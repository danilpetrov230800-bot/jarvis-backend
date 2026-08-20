# NOVA Windows Build Script
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "=== NOVA Windows Build ==="

Write-Host "[1/5] Installing backend dependencies..."
Set-Location backend
pip install -r requirements.txt -q
Set-Location ..

Write-Host "[2/5] Running self-test..."
python tests/self_test.py

Write-Host "[3/5] Running unit tests..."
Set-Location backend
pytest ../tests/unit/ -v --tb=short
Set-Location ..

Write-Host "[4/5] Building frontend..."
Set-Location frontend
npm install --silent
npm run build

Write-Host "[5/5] Building Windows installer..."
npx electron-builder --win --x64

Set-Location ..
Write-Host "=== Build complete ==="
Get-ChildItem release/
