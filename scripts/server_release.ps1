param(
    [ValidateSet("Inspect", "Apply", "Rollback")]
    [string]$Mode = "Inspect",
    [string]$PackagePath = "",
    [string]$ExpectedSHA256 = "",
    [string]$InstallRoot = "E:\AI-Creative-Studio",
    [string]$RollbackId = ""
)

$ErrorActionPreference = "Stop"

function Get-FileDigest([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace("-", "").ToLowerInvariant()
    } finally {
        $sha.Dispose()
        $stream.Dispose()
    }
}

function Assert-SafeRelativePath([string]$Path) {
    $value = $Path.Replace("\", "/").TrimStart("/")
    if (-not $value -or
        $value -ne $Path.Replace("\", "/") -or
        $value -match '^[a-zA-Z]:' -or
        $value -match '(^|/)\.\.(/|$)') {
        throw "Unsafe package path: $Path"
    }
    if ($value -match '(^|/)(\.env|\.venv|\.scratch|data|images|uploads|logs|staging|private)(/|$)') {
        throw "Protected path is not allowed in a release package: $Path"
    }
    return $value
}

function Assert-PortsStopped {
    $listeners = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalPort -in 8775, 8780 })
    if ($listeners.Count -gt 0) {
        $summary = ($listeners | ForEach-Object { "{0}:{1} pid={2}" -f $_.LocalAddress, $_.LocalPort, $_.OwningProcess }) -join "; "
        throw "Stop the web service and AI gateway before changing code. Active listeners: $summary"
    }
}

function Read-ReleaseCandidate([string]$Archive, [string]$ExpectedHash, [string]$StagingRoot) {
    if (-not (Test-Path -LiteralPath $Archive -PathType Leaf)) {
        throw "Release package was not found: $Archive"
    }
    if ($ExpectedHash -notmatch '^[a-fA-F0-9]{64}$') {
        throw "ExpectedSHA256 must contain exactly 64 hexadecimal characters."
    }
    $actualHash = Get-FileDigest $Archive
    if ($actualHash -ne $ExpectedHash.ToLowerInvariant()) {
        throw "Release package SHA-256 does not match. Expected $ExpectedHash, got $actualHash"
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archiveObject = [IO.Compression.ZipFile]::OpenRead((Resolve-Path -LiteralPath $Archive).Path)
    try {
        foreach ($entry in $archiveObject.Entries) {
            if ($entry.FullName.EndsWith("/")) { continue }
            Assert-SafeRelativePath $entry.FullName | Out-Null
        }
    } finally {
        $archiveObject.Dispose()
    }

    $candidate = Join-Path $StagingRoot ("candidate-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $candidate | Out-Null
    Expand-Archive -LiteralPath $Archive -DestinationPath $candidate -Force
    $manifestPath = Join-Path $candidate "release-manifest.json"
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw "release-manifest.json is missing from the package."
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($manifest.schema_version -ne "creative-studio-release.v1" -or $manifest.git_commit -notmatch '^[a-f0-9]{40}$') {
        throw "Release manifest identity is invalid."
    }

    $expectedPaths = @{}
    foreach ($entry in @($manifest.files)) {
        $relative = Assert-SafeRelativePath ([string]$entry.path)
        if ($expectedPaths.ContainsKey($relative)) {
            throw "Release manifest contains duplicate path: $relative"
        }
        $expectedPaths[$relative] = $true
        $file = Join-Path $candidate $relative.Replace("/", "\")
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
            throw "Release file is missing: $relative"
        }
        $item = Get-Item -LiteralPath $file
        if ([long]$entry.bytes -ne [long]$item.Length -or [string]$entry.sha256 -ne (Get-FileDigest $file)) {
            throw "Release file verification failed: $relative"
        }
    }
    $actualFiles = @(Get-ChildItem -LiteralPath $candidate -File -Recurse -Force |
        ForEach-Object { $_.FullName.Substring($candidate.Length + 1).Replace("\", "/") } |
        Where-Object { $_ -ne "release-manifest.json" })
    $unexpected = @($actualFiles | Where-Object { -not $expectedPaths.ContainsKey($_) })
    if ($unexpected.Count -gt 0) {
        throw "Package contains files not listed in its manifest: $($unexpected -join ', ')"
    }
    $inventoryScript = Join-Path $candidate "scripts\code_inventory.ps1"
    $inventory = & $inventoryScript -Root $candidate
    if ([string]$inventory.AggregateSHA256 -ne [string]$manifest.code_inventory.aggregate_sha256) {
        throw "Package code inventory does not match release manifest."
    }
    return [pscustomobject]@{ Candidate = $candidate; Manifest = $manifest; PackageSHA256 = $actualHash }
}

$installPath = [IO.Path]::GetFullPath($InstallRoot).TrimEnd("\")
$stagingRoot = Join-Path $installPath "staging\releases"
$rollbackRoot = Join-Path $installPath "staging\rollbacks"
New-Item -ItemType Directory -Force -Path $stagingRoot, $rollbackRoot | Out-Null

if ($Mode -eq "Rollback") {
    if ($RollbackId -notmatch '^[a-zA-Z0-9._-]+$') {
        throw "RollbackId is required and must be a simple directory name."
    }
    Assert-PortsStopped
    $rollbackPath = Join-Path $rollbackRoot $RollbackId
    $rollbackManifestPath = Join-Path $rollbackPath "rollback-manifest.json"
    if (-not (Test-Path -LiteralPath $rollbackManifestPath -PathType Leaf)) {
        throw "Rollback manifest was not found: $rollbackManifestPath"
    }
    $rollback = Get-Content -LiteralPath $rollbackManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($relative in @($rollback.created_files)) {
        $safe = Assert-SafeRelativePath ([string]$relative)
        $target = Join-Path $installPath $safe.Replace("/", "\")
        if (Test-Path -LiteralPath $target -PathType Leaf) { Remove-Item -LiteralPath $target -Force }
    }
    foreach ($relative in @($rollback.backed_up_files)) {
        $safe = Assert-SafeRelativePath ([string]$relative)
        $source = Join-Path $rollbackPath ("files\" + $safe.Replace("/", "\"))
        $target = Join-Path $installPath $safe.Replace("/", "\")
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        Copy-Item -LiteralPath $source -Destination $target -Force
    }
    $oldManifest = Join-Path $rollbackPath "previous-release-manifest.json"
    $liveManifest = Join-Path $installPath "release-manifest.json"
    if (Test-Path -LiteralPath $oldManifest) {
        Copy-Item -LiteralPath $oldManifest -Destination $liveManifest -Force
    } elseif (Test-Path -LiteralPath $liveManifest) {
        Remove-Item -LiteralPath $liveManifest -Force
    }
    [pscustomobject]@{ Status = "rolled_back"; RollbackId = $RollbackId; RestartRequired = $true }
    exit 0
}

if (-not $PackagePath) { throw "PackagePath is required for Inspect and Apply." }
$candidateInfo = Read-ReleaseCandidate $PackagePath $ExpectedSHA256 $stagingRoot
$manifest = $candidateInfo.Manifest
if ($Mode -eq "Inspect") {
    [pscustomobject]@{
        Status = "verified"
        ReleaseId = $manifest.release_id
        GitCommit = $manifest.git_commit
        PackageSHA256 = $candidateInfo.PackageSHA256
        CodeFileCount = $manifest.code_inventory.file_count
        CodeSHA256 = $manifest.code_inventory.aggregate_sha256
        ApplyCommandRequired = $true
    }
    exit 0
}

Assert-PortsStopped
$rollbackId = "{0}-before-{1}" -f (Get-Date -Format "yyyyMMdd-HHmmss"), $manifest.release_id
$rollbackPath = Join-Path $rollbackRoot $rollbackId
$rollbackFiles = Join-Path $rollbackPath "files"
New-Item -ItemType Directory -Force -Path $rollbackFiles | Out-Null

$newPaths = @($manifest.files | ForEach-Object { Assert-SafeRelativePath ([string]$_.path) })
$liveManifestPath = Join-Path $installPath "release-manifest.json"
$oldPaths = @()
if (Test-Path -LiteralPath $liveManifestPath -PathType Leaf) {
    Copy-Item -LiteralPath $liveManifestPath -Destination (Join-Path $rollbackPath "previous-release-manifest.json")
    $oldManifest = Get-Content -LiteralPath $liveManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $oldPaths = @($oldManifest.files | ForEach-Object { Assert-SafeRelativePath ([string]$_.path) })
}
$managedPaths = @($newPaths + $oldPaths | Sort-Object -Unique)
$backedUp = @()
$created = @()
foreach ($relative in $managedPaths) {
    $target = Join-Path $installPath $relative.Replace("/", "\")
    if (Test-Path -LiteralPath $target -PathType Leaf) {
        $backup = Join-Path $rollbackFiles $relative.Replace("/", "\")
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backup) | Out-Null
        Copy-Item -LiteralPath $target -Destination $backup -Force
        $backedUp += $relative
    } elseif ($newPaths -contains $relative) {
        $created += $relative
    }
}
$rollbackManifest = [ordered]@{
    schema_version = "creative-studio-rollback.v1"
    rollback_id = $rollbackId
    target_release_id = $manifest.release_id
    created_at = (Get-Date).ToUniversalTime().ToString("o")
    backed_up_files = $backedUp
    created_files = $created
}
[IO.File]::WriteAllText((Join-Path $rollbackPath "rollback-manifest.json"), ($rollbackManifest | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))

foreach ($relative in @($oldPaths | Where-Object { $newPaths -notcontains $_ })) {
    $target = Join-Path $installPath $relative.Replace("/", "\")
    if (Test-Path -LiteralPath $target -PathType Leaf) { Remove-Item -LiteralPath $target -Force }
}
foreach ($entry in @($manifest.files)) {
    $relative = Assert-SafeRelativePath ([string]$entry.path)
    $source = Join-Path $candidateInfo.Candidate $relative.Replace("/", "\")
    $target = Join-Path $installPath $relative.Replace("/", "\")
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
    Copy-Item -LiteralPath $source -Destination $target -Force
}
Copy-Item -LiteralPath (Join-Path $candidateInfo.Candidate "release-manifest.json") -Destination $liveManifestPath -Force

$python = Join-Path $installPath ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Code was applied but the server virtual environment is missing: $python. Use rollback $rollbackId before restarting."
}
& $python -m pip install -r (Join-Path $installPath "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Dependency installation failed. Keep services stopped and run rollback $rollbackId."
}

[pscustomobject]@{
    Status = "applied"
    ReleaseId = $manifest.release_id
    GitCommit = $manifest.git_commit
    RollbackId = $rollbackId
    ProtectedDataUntouched = $true
    RestartRequired = $true
}
