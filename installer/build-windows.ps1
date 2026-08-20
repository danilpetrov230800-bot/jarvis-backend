param(
    [string]$Version = "1.5.0"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Build = Join-Path $Root "build"
$Dist = Join-Path $Root "dist"
$Release = Join-Path $Root "release"

Remove-Item $Build, $Dist -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Release | Out-Null

python -m pip install --upgrade pip
python -m pip install -r (Join-Path $Root "requirements-dev.txt")

python -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --name NOVA `
  --paths $Root `
  --add-data "$Root\static;static" `
  --collect-all edge_tts `
  --collect-all webview `
  --hidden-import uvicorn.logging `
  --hidden-import uvicorn.loops.auto `
  --hidden-import uvicorn.protocols.http.auto `
  --hidden-import uvicorn.protocols.websockets.auto `
  (Join-Path $Root "nova_launcher.py")

& iscc "/DAppVersion=$Version" (Join-Path $PSScriptRoot "NOVA.iss")
Copy-Item (Join-Path $Dist "NOVA-Setup.exe") (Join-Path $Release "NOVA-Setup.exe") -Force
Compress-Archive -Path (Join-Path $Dist "NOVA\*") -DestinationPath (Join-Path $Release "NOVA-Portable.zip") -Force
Get-FileHash (Join-Path $Release "NOVA-Setup.exe") -Algorithm SHA256 |
  ForEach-Object { "$($_.Hash)  NOVA-Setup.exe" } |
  Set-Content (Join-Path $Release "SHA256.txt") -Encoding ascii
