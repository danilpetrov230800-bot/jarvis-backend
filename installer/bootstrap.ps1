# NOVA Windows bootstrap. ASCII-only so cmd/PowerShell never split lines.
param(
    [switch]$SkipRun,
    [switch]$SkipShortcut
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = "SilentlyContinue"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RuntimeDir = Join-Path $Root "runtime"
$Python = Join-Path $RuntimeDir "python.exe"
$Req = Join-Path $Root "requirements.txt"
$HashFile = Join-Path $RuntimeDir ".deps-hash"
$PythonVersion = "3.12.10"
$PythonZipName = "python-$PythonVersion-embed-amd64.zip"
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/$PythonZipName"
$GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host ">>> $Message" -ForegroundColor Magenta
}

function Unblock-Tree([string]$Path) {
    Get-ChildItem -Path $Path -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
        try { Unblock-File -Path $_.FullName -ErrorAction SilentlyContinue } catch { }
    }
}

function Get-FileSha256([string]$Path) {
    return (Get-FileHash -Path $Path -Algorithm SHA256).Hash
}

function Enable-ProjectPath {
    if (-not (Test-Path $RuntimeDir)) { return }
    $pth = Get-ChildItem $RuntimeDir -Filter "python*._pth" | Select-Object -First 1
    if (-not $pth) { return }
    $lines = New-Object System.Collections.Generic.List[string]
    $hasParent = $false
    $hasSite = $false
    foreach ($line in (Get-Content -Path $pth.FullName)) {
        $trim = $line.Trim()
        if ($trim -eq "#import site") {
            $lines.Add("import site")
            $hasSite = $true
            continue
        }
        if ($trim -eq "..") { $hasParent = $true }
        if ($trim -eq "import site") { $hasSite = $true }
        if ($trim -ne "") { $lines.Add($trim) }
    }
    if (-not $hasParent) { $lines.Add("..") }
    if (-not $hasSite) { $lines.Add("import site") }
    Set-Content -Path $pth.FullName -Value ($lines -join "`r`n") -Encoding ASCII
}

function Install-PortablePython {
    if (Test-Path $Python) { return }
    Write-Step "Downloading portable Python $PythonVersion..."
    New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
    $zip = Join-Path $RuntimeDir $PythonZipName
    Invoke-WebRequest -Uri $PythonUrl -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath $RuntimeDir -Force
    Remove-Item $zip -Force

    $pth = Get-ChildItem $RuntimeDir -Filter "python*._pth" | Select-Object -First 1
    if (-not $pth) { throw "python*._pth not found. Python zip is damaged." }
    $content = Get-Content -Path $pth.FullName -Raw
    $content = $content -replace "#import site", "import site"
    if ($content -notmatch "(?m)^import site") {
        $content = $content.TrimEnd() + "`r`nimport site`r`n"
    }
    Set-Content -Path $pth.FullName -Value $content -Encoding ASCII
    Enable-ProjectPath

    Write-Step "Installing pip..."
    $getPip = Join-Path $RuntimeDir "get-pip.py"
    Invoke-WebRequest -Uri $GetPipUrl -OutFile $getPip -UseBasicParsing
    & $Python $getPip --no-warn-script-location
    Remove-Item $getPip -Force -ErrorAction SilentlyContinue
}

function Install-Dependencies {
    if (-not (Test-Path $Req)) { throw "requirements.txt is missing" }
    $hash = Get-FileSha256 $Req
    if ((Test-Path $HashFile) -and ((Get-Content $HashFile -Raw).Trim() -eq $hash)) {
        return
    }
    Write-Step "Installing NOVA libraries..."
    & $Python -m pip install --upgrade pip --no-warn-script-location
    & $Python -m pip install -r $Req --no-warn-script-location
    if ($LASTEXITCODE -ne 0) { throw "pip install failed." }
    Set-Content -Path $HashFile -Value $hash -Encoding ASCII
}

function Install-Shortcut {
    if ($SkipShortcut) { return }
    $desktop = [Environment]::GetFolderPath("Desktop")
    if (-not $desktop) { return }
    $launcher = Join-Path $Root "NOVA.bat"
    if (-not (Test-Path $launcher)) { $launcher = Join-Path $Root "JARVIS.bat" }
    $lnkPath = Join-Path $desktop "NOVA.lnk"
    $wsh = New-Object -ComObject WScript.Shell
    $shortcut = $wsh.CreateShortcut($lnkPath)
    $shortcut.TargetPath = $launcher
    $shortcut.WorkingDirectory = $Root
    $shortcut.WindowStyle = 1
    $shortcut.Description = "NOVA personal AI assistant"
    $shortcut.Save()
    Write-Host "Shortcut: $lnkPath" -ForegroundColor Green
}

function Start-Nova {
    if (-not (Test-Path (Join-Path $Root ".env")) -and (Test-Path (Join-Path $Root ".env.example"))) {
        Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
    }
    Write-Step "Starting NOVA..."
    Set-Location $Root
    $env:PYTHONPATH = $Root
    Enable-ProjectPath
    New-Item -ItemType Directory -Force -Path (Join-Path $Root "data") | Out-Null
    Write-Host "NOVA UI: http://127.0.0.1:8080"
    Write-Host "Keep this window open."
    & $Python (Join-Path $Root "run.py")
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Python exited with code $LASTEXITCODE"
        Write-Host "Log: $(Join-Path $Root 'data\nova.log')"
        exit $LASTEXITCODE
    }
}

Unblock-Tree $Root
Install-PortablePython
Enable-ProjectPath
Install-Dependencies
Install-Shortcut
if (-not $SkipRun) {
    Start-Nova
}
