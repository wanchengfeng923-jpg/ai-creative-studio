param(
    [string]$Ref = "HEAD",
    [string]$OutputDirectory = ".release",
    [switch]$AllowDirty
)

$ErrorActionPreference = "Stop"

function Invoke-Checked([string]$Description, [scriptblock]$Command) {
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE"
    }
}

function Get-FileDigest([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

$repositoryRoot = (& git rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0 -or -not $repositoryRoot) {
    throw "Run this script inside the AI Creative Studio Git repository."
}
$repositoryRoot = (Resolve-Path -LiteralPath $repositoryRoot).Path
Set-Location $repositoryRoot

$dirty = @(& git status --porcelain --untracked-files=all)
if ($dirty.Count -gt 0 -and -not $AllowDirty) {
    throw "The worktree is not clean. Commit or preserve current work first. Use -AllowDirty only to package an already committed ref while knowingly ignoring local changes."
}

$commit = (& git rev-parse "$Ref`^{commit}").Trim()
if ($LASTEXITCODE -ne 0 -or -not $commit) {
    throw "Git ref does not resolve to a commit: $Ref"
}
$shortCommit = $commit.Substring(0, 12)
$releaseId = "{0}-{1}" -f (Get-Date -Format "yyyyMMdd-HHmmss"), $shortCommit
$outputRoot = [IO.Path]::GetFullPath((Join-Path $repositoryRoot $OutputDirectory))
New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null

$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("creative-studio-release-" + [Guid]::NewGuid().ToString("N"))
$checkout = Join-Path $tempRoot "checkout"
$payload = Join-Path $tempRoot "payload"
$sourceArchive = Join-Path $tempRoot "source.zip"
$packagePath = Join-Path $outputRoot ("ai-creative-studio-{0}.zip" -f $releaseId)
$manifestPath = Join-Path $outputRoot ("ai-creative-studio-{0}.manifest.json" -f $releaseId)
$checksumPath = "$packagePath.sha256"

$releasePaths = @(
    ".gitattributes",
    "README.md",
    "CHANGELOG.md",
    "requirements.txt",
    "launcher.py",
    "proxy_relay.py",
    "proxy_workbench.py",
    ":(top,glob)*.bat",
    "src",
    "static",
    "config",
    "chat2api",
    "tests",
    "scripts/code_inventory.ps1",
    "scripts/server_release.ps1",
    "docs/operations.md",
    "docs/deployment/public-startup-guide.md",
    "docs/deployment/release-workflow.md"
)
$requiredReleasePaths = @("requirements.txt", "launcher.py", "src", "static", "config", "chat2api", "tests")
$availableReleasePaths = @()
foreach ($path in $releasePaths) {
    if ($path.StartsWith(":(")) {
        $availableReleasePaths += $path
        continue
    }
    $found = @(& git ls-tree --name-only $commit -- $path)
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect release path in ${Ref}: $path"
    }
    if ($found.Count -gt 0) {
        $availableReleasePaths += $path
    } elseif ($requiredReleasePaths -contains $path) {
        throw "Required release path is missing from ${Ref}: $path"
    }
}

try {
    New-Item -ItemType Directory -Force -Path $tempRoot, $payload | Out-Null
    Invoke-Checked "Creating detached verification checkout" {
        git worktree add --detach $checkout $commit
    }

    $python = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python)) {
        throw "Project Python was not found: $python"
    }
    $previousPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = Join-Path $checkout "src"
        Push-Location $checkout
        try {
            Invoke-Checked "Full unit test suite" {
                & $python -m unittest discover -s tests -q
            }
            Invoke-Checked "Release gate" {
                & $python -m creative_studio.ai_v2.release_gate
            }
        } finally {
            Pop-Location
        }
    } finally {
        $env:PYTHONPATH = $previousPythonPath
    }

    Invoke-Checked "Creating Git archive" {
        git archive --format=zip --output=$sourceArchive $commit -- @availableReleasePaths
    }
    Expand-Archive -LiteralPath $sourceArchive -DestinationPath $payload -Force

    $inventoryScript = Join-Path $payload "scripts\code_inventory.ps1"
    $inventoryPath = Join-Path $tempRoot "code-inventory.json"
    $inventory = & $inventoryScript -Root $payload -OutputPath $inventoryPath

    $files = @(Get-ChildItem -LiteralPath $payload -File -Recurse -Force | Sort-Object FullName | ForEach-Object {
        [ordered]@{
            path = $_.FullName.Substring($payload.Length + 1).Replace("\", "/")
            bytes = [long]$_.Length
            sha256 = Get-FileDigest $_.FullName
        }
    })
    $manifest = [ordered]@{
        schema_version = "creative-studio-release.v1"
        release_id = $releaseId
        git_ref = $Ref
        git_commit = $commit
        created_at = (Get-Date).ToUniversalTime().ToString("o")
        code_inventory = [ordered]@{
            schema_version = "creative-studio-code-inventory.v2"
            file_count = [int]$inventory.FileCount
            normalized_bytes = [long]$inventory.TotalBytes
            aggregate_sha256 = [string]$inventory.AggregateSHA256
        }
        files = $files
    }
    $manifestJson = $manifest | ConvertTo-Json -Depth 6
    $payloadManifest = Join-Path $payload "release-manifest.json"
    [IO.File]::WriteAllText($payloadManifest, $manifestJson, [Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText($manifestPath, $manifestJson, [Text.UTF8Encoding]::new($false))

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    if (Test-Path -LiteralPath $packagePath) {
        Remove-Item -LiteralPath $packagePath -Force
    }
    [IO.Compression.ZipFile]::CreateFromDirectory($payload, $packagePath, [IO.Compression.CompressionLevel]::Optimal, $false)
    $packageHash = Get-FileDigest $packagePath
    [IO.File]::WriteAllText($checksumPath, "$packageHash  $([IO.Path]::GetFileName($packagePath))`n", [Text.UTF8Encoding]::new($false))

    [pscustomobject]@{
        ReleaseId = $releaseId
        GitCommit = $commit
        PackagePath = $packagePath
        PackageSHA256 = $packageHash
        ManifestPath = $manifestPath
        CodeFileCount = $inventory.FileCount
        CodeSHA256 = $inventory.AggregateSHA256
    }
} finally {
    if (Test-Path -LiteralPath $checkout) {
        git worktree remove --force $checkout 2>$null
    }
    if (Test-Path -LiteralPath $tempRoot) {
        $resolvedTemp = (Resolve-Path -LiteralPath $tempRoot).Path
        $resolvedSystemTemp = (Resolve-Path -LiteralPath ([IO.Path]::GetTempPath())).Path.TrimEnd("\")
        if ($resolvedTemp.StartsWith($resolvedSystemTemp + "\", [StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $resolvedTemp -Recurse -Force
        }
    }
}
