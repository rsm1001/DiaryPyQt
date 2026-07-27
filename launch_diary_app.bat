@echo off
chcp 65001 > nul
setlocal

set "PROJECT_ROOT=%~dp0"
set "VENV_PYTHON=%PROJECT_ROOT%.venv\Scripts\python.exe"

cd /d "%PROJECT_ROOT%"
if errorlevel 1 (
    echo Error: Cannot access the project directory
    pause
    exit /b 1
)

echo.
echo DiaryPyQt Application - Launcher
echo ==============================
echo.

rem Create the project-local virtual environment when needed.
if not exist "%VENV_PYTHON%" (
    echo Creating project virtual environment with the Python launcher...
    py -3 -m venv "%PROJECT_ROOT%.venv"
)

if not exist "%VENV_PYTHON%" (
    echo Trying Python from PATH...
    python -m venv "%PROJECT_ROOT%.venv"
)

if not exist "%VENV_PYTHON%" (
    echo 请安装 Python 3.8+ 并加入 PATH
    pause
    exit /b 1
)

"%VENV_PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)" > nul 2>&1
if errorlevel 1 (
    echo 请安装 Python 3.8+ 并加入 PATH
    pause
    exit /b 1
)

rem Install or update the dependencies in the project-local environment.
echo Installing dependencies...
"%VENV_PYTHON%" -m pip install -r "%PROJECT_ROOT%requirements.txt"
if errorlevel 1 (
    echo Dependency installation failed
    pause
    exit /b 1
)

rem Run main program
echo Starting DiaryPyQt Application...
"%VENV_PYTHON%" "%PROJECT_ROOT%main.py"

pause