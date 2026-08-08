param(
    [string]$VenvName = ".venv311",
    [switch]$Dev,
    [ValidateSet("auto", "cpu", "nvidia")]
    [string]$TorchVariant = "auto"
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

if ($TorchVariant -eq "auto") {
    $NvidiaSmi = Get-Command "nvidia-smi" -ErrorAction SilentlyContinue
    $TorchVariant = if ($null -ne $NvidiaSmi) { "nvidia" } else { "cpu" }
}

$RequirementsFile = if ($TorchVariant -eq "nvidia") { "requirements.txt" } else { "requirements-cpu.txt" }
Write-Host "Perfil de processamento selecionado: $TorchVariant"

& $VenvPython -m pip install --upgrade pip setuptools wheel
& $VenvPython -m pip install -r $RequirementsFile
if ($Dev) {
    & $VenvPython -m pip install -r "requirements-dev-tools.txt"
}
& $VenvPython -m pip install --no-deps -e .

& $VenvPython -c "import torch; print('PyTorch', torch.__version__, '| CUDA:', torch.version.cuda or 'não', '| GPU disponível:', torch.cuda.is_available())"

Write-Host "Instalação concluída."
Write-Host "Ative com: .\$VenvName\Scripts\Activate.ps1"
