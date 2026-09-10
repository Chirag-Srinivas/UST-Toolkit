param(
    [string]$RunDirectory,
    [switch]$CacheOnly,
    [switch]$ExtractMissingIterations,
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8765,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$moduleRoot = Split-Path -Parent $PSScriptRoot
$projectRoot = Split-Path -Parent $moduleRoot
$modulePython = Join-Path $projectRoot "venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $modulePython)) {
    $modulePython = "python"
}

Set-Location -LiteralPath $moduleRoot
$moduleArguments = @(
    "-m", "module5", "serve",
    "--host", $HostAddress,
    "--port", $Port
)
if ($RunDirectory) {
    $moduleArguments += @("--run-dir", $RunDirectory)
}
if ($CacheOnly) {
    $moduleArguments += "--cache-only"
}
if ($ExtractMissingIterations) {
    $moduleArguments += "--extract-missing-iterations"
}
if ($NoBrowser) {
    $moduleArguments += "--no-browser"
}

& $modulePython @moduleArguments
