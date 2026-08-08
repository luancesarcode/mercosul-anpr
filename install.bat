@echo off
setlocal
set VENV=.venv311
set TORCH_VARIANT=auto
set DEV=0

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--dev" set DEV=1
if /I "%~1"=="--cpu" set TORCH_VARIANT=cpu
if /I "%~1"=="--nvidia" set TORCH_VARIANT=nvidia
shift
goto parse_args
:args_done

if /I "%TORCH_VARIANT%"=="auto" (
  where nvidia-smi >nul 2>&1
  if errorlevel 1 (
    set TORCH_VARIANT=cpu
  ) else (
    set TORCH_VARIANT=nvidia
  )
)

if /I "%TORCH_VARIANT%"=="nvidia" (
  set REQUIREMENTS=requirements.txt
) else (
  set REQUIREMENTS=requirements-cpu.txt
)
echo Perfil de processamento selecionado: %TORCH_VARIANT%

if not exist "%VENV%\Scripts\python.exe" (
  python -m venv %VENV%
)

"%VENV%\Scripts\python.exe" -c "import encodings" >nul 2>&1
if errorlevel 1 (
  echo O ambiente virtual existente esta invalido. Recriando...
  python -m venv --clear %VENV%
)

"%VENV%\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
"%VENV%\Scripts\python.exe" -m pip install -r %REQUIREMENTS%
if "%DEV%"=="1" "%VENV%\Scripts\python.exe" -m pip install -r requirements-dev-tools.txt
"%VENV%\Scripts\python.exe" -m pip install --no-deps -e .
"%VENV%\Scripts\python.exe" -c "import torch; print('PyTorch', torch.__version__, '| CUDA:', torch.version.cuda or 'nao', '| GPU disponivel:', torch.cuda.is_available())"
echo Instalacao concluida.
echo Ative com: %VENV%\Scripts\activate.bat
endlocal
