@echo off
set VENV=.venv311
if not exist %VENV% (
  python -m venv %VENV%
)
%VENV%\Scripts\python.exe -m pip install --upgrade pip
%VENV%\Scripts\python.exe -m pip install -r requirements.txt
echo Instalacao concluida.
echo Ative com: %VENV%\Scripts\activate.bat
