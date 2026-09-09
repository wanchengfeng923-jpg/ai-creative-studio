param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$rootPath = (Resolve-Path -LiteralPath $Root).Path.TrimEnd("\")
$includedDirectories = @("src", "static", "config", "chat2api", "tests")
$includedFiles = @(
    "launcher.py",
    "proxy_relay.py",
    "proxy_workbench.py",
    "requirements.txt"
)
$excludedPattern = "\\(?:\.venv|__pycache__|\.pytest_cache|node_modules|dist|images|image_job_state|private)(?:\\|$)|\\\.env$|\.pyc$"
$canonicalTextExtensions = @(
    ".bat", ".css", ".html", ".js", ".json", ".md", ".ps1", ".py",
    ".toml", ".ts", ".tsx", ".txt", ".yaml", ".yml"
)
$utf8 = [Text.UTF8Encoding]::new($false, $true)

function Get-SHA256([byte[]]$Bytes) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash($Bytes))).Replace("-", "").ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}

$files = @()
foreach ($directory in $includedDirectories) {
    $path = Join-Path $rootPath $directory
    if (Test-Path -LiteralPath $path) {
        $files += Get-ChildItem -LiteralPath $path -File -Recurse -Force |
            Where-Object { $_.FullName -notmatch $excludedPattern }
    }
}
foreach ($file in $includedFiles) {
    $path = Join-Path $rootPath $file
    if (Test-Path -LiteralPath $path) {
        $files += Get-Item -LiteralPath $path
    }
}
$files += Get-ChildItem -LiteralPath $rootPath -File -Force |
    Where-Object { $_.Extension -ieq ".bat" }

$entries = @($files | Sort-Object FullName | ForEach-Object {
    $rawBytes = [IO.File]::ReadAllBytes($_.FullName)
    $canonicalBytes = $rawBytes
    if ($canonicalTextExtensions -contains $_.Extension.ToLowerInvariant()) {
        try {
            $text = $utf8.GetString($rawBytes)
            $canonicalText = $text.Replace("`r`n", "`n").Replace("`r", "`n")
            $canonicalBytes = [Text.UTF8Encoding]::new($false).GetBytes($canonicalText)
        } catch [Text.DecoderFallbackException] {
            $canonicalBytes = $rawBytes
        }
    }
    [pscustomobject]@{
        path = $_.FullName.Substring($rootPath.Length + 1).Replace("\", "/")
        sha256 = Get-SHA256 $canonicalBytes
        bytes = $canonicalBytes.Length
        raw_sha256 = Get-SHA256 $rawBytes
        raw_bytes = $rawBytes.Length
    }
})

$canonical = [string]::Join("`n", @($entries | ForEach-Object {
    "{0}`t{1}`t{2}" -f $_.path, $_.sha256, $_.bytes
}))
$aggregate = Get-SHA256 ([Text.Encoding]::UTF8.GetBytes($canonical))

$inventory = [ordered]@{
    schema_version = "creative-studio-code-inventory.v2"
    root = $rootPath
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    file_count = $entries.Count
    total_bytes = [long](($entries | Measure-Object -Property bytes -Sum).Sum)
    raw_total_bytes = [long](($entries | Measure-Object -Property raw_bytes -Sum).Sum)
    aggregate_sha256 = $aggregate
    entries = $entries
}

if ($OutputPath) {
    if ([IO.Path]::IsPathRooted($OutputPath)) {
        $resolvedOutput = [IO.Path]::GetFullPath($OutputPath)
    } else {
        $resolvedOutput = [IO.Path]::GetFullPath((Join-Path (Get-Location).Path $OutputPath))
    }
    $outputDirectory = Split-Path -Parent $resolvedOutput
    if ($outputDirectory) {
        New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
    }
    [IO.File]::WriteAllText(
        $resolvedOutput,
        ($inventory | ConvertTo-Json -Depth 5),
        [Text.UTF8Encoding]::new($false)
    )
}

[pscustomobject]@{
    Root = $inventory.root
    FileCount = $inventory.file_count
    TotalBytes = $inventory.total_bytes
    RawTotalBytes = $inventory.raw_total_bytes
    AggregateSHA256 = $inventory.aggregate_sha256
    OutputPath = if ($OutputPath) { $resolvedOutput } else { $null }
}
