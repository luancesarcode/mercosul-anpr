param(
    [string]$VenvName = ".venv311"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $VenvName)) {
    python -m venv $VenvName
}

& "$VenvName\Scripts\python.exe" -m pip install --upgrade pip
& "$VenvName\Scripts\python.exe" -m pip install -r requirements.txt

Write-Host "Instalacao concluida."
Write-Host "Ative com: .\$VenvName\Scripts\Activate.ps1"
