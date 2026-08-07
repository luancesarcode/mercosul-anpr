@echo off
setlocal
set VENV=.venv311
set REQUIREMENTS=requirements.txt
set TORCH_VARIANT=cpu

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--dev" set REQUIREMENTS=requirements-dev.txt
if /I "%~1"=="--standard-torch" set TORCH_VARIANT=standard
shift
goto parse_args
:args_done

if not exist "%VENV%\Scripts\python.exe" (
  python -m venv %VENV%
)

"%VENV%\Scripts\python.exe" -c "import encodings" >nul 2>&1
if errorlevel 1 (
  echo O ambiente virtual existente esta invalido. Recriando...
  python -m venv --clear %VENV%
)

"%VENV%\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if /I "%TORCH_VARIANT%"=="cpu" (
  "%VENV%\Scripts\python.exe" -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.5.1+cpu torchvision==0.20.1+cpu
)
"%VENV%\Scripts\python.exe" -m pip install -r %REQUIREMENTS%
"%VENV%\Scripts\python.exe" -m pip install --no-deps -e .
echo Instalacao concluida.
echo Ative com: %VENV%\Scripts\activate.bat
endlocal
