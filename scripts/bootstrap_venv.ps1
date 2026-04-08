# Install Sokol Python dependencies into the active venv.
# Usage: .\scripts\bootstrap_venv.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
& python -m pip install --upgrade pip
& python -m pip install -r requirements.txt
Write-Host "Done. Run: python run.py --skip-admin-check"
