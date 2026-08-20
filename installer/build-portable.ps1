# Build a ready-to-run Windows folder (source + portable Python + libs).
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Dist = Join-Path $Root "dist"
$Stage = Join-Path $Dist "NOVA"
$Zip = Join-Path $Dist "NOVA-windows.zip"

if (Test-Path $Dist) { Remove-Item $Dist -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

$copy = @(
    "NOVA.bat",
    "NOVA.vbs",
    "JARVIS.bat",
    "run.py",
    "requirements.txt",
    ".env.example",
    "README.md",
    "INSTALL.md",
    "КАК ЗАПУСТИТЬ.txt",
    "start.bat",
    "start.sh"
)
foreach ($name in $copy) {
    $src = Join-Path $Root $name
    if (Test-Path $src) { Copy-Item $src $Stage }
}
foreach ($dir in @("jarvis", "static", "installer", "api", "data", "docs")) {
    $src = Join-Path $Root $dir
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $Stage $dir) -Recurse
    }
}

Get-ChildItem $Stage -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
@(
    "data\nova.db",
    "data\settings.json",
    "data\permissions.json",
    "data\nova.log"
) | ForEach-Object {
    $p = Join-Path $Stage $_
    if (Test-Path $p) { Remove-Item $p -Force -ErrorAction SilentlyContinue }
}
if (Test-Path (Join-Path $Stage "data\backups")) {
    Remove-Item (Join-Path $Stage "data\backups") -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Installing portable runtime into $Stage"
$bootstrap = Join-Path $Stage "installer\bootstrap.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File $bootstrap -SkipRun -SkipShortcut

if (Test-Path $Zip) { Remove-Item $Zip -Force }
Compress-Archive -Path $Stage -DestinationPath $Zip -Force
Write-Host "Packed: $Zip"
