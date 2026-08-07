param(
    [string]$VenvName = ".venv311",
    [switch]$Dev,
    [ValidateSet("cpu", "standard")]
    [string]$TorchVariant = "cpu"
)

$ErrorActionPreference = "Stop"
$VenvPython = Join-Path $VenvName "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    python -m venv $VenvName
}

& $VenvPython -c "import encodings" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "O ambiente virtual existente está inválido. Recriando..."
    python -m venv --clear $VenvName
}

$RequirementsFile = if ($Dev) { "requirements-dev.txt" } else { "requirements.txt" }
& $VenvPython -m pip install --upgrade pip setuptools wheel
if ($TorchVariant -eq "cpu") {
    & $VenvPython -m pip install `
        --index-url https://download.pytorch.org/whl/cpu `
        torch==2.5.1+cpu `
        torchvision==0.20.1+cpu
}
& $VenvPython -m pip install -r $RequirementsFile
& $VenvPython -m pip install --no-deps -e .

Write-Host "Instalação concluída."
Write-Host "Ative com: .\$VenvName\Scripts\Activate.ps1"
