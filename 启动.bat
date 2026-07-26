@echo off
title XAOCEN ImgTor

:: Find user's Python (skip OpenClaw bundled one)
set PYTHON=
for %%p in (python python3) do (
    %%p --version >nul 2>&1
    if not errorlevel 1 (
        %%p -c "import tkinter" >nul 2>&1
        if not errorlevel 1 set PYTHON=%%p
    )
)

if "%PYTHON%"=="" (
    echo [ERR] Python with tkinter not found.
    echo Please install Python 3.8+ from https://www.python.org/
    pause
    exit /b 1
)

echo [INFO] Using %PYTHON%

:: Keep generated Python bytecode out of the project tree; runtime files live in archive/runtime.
set PYTHONDONTWRITEBYTECODE=1
set PYTHONPATH=%~dp0src;%PYTHONPATH%

:: Install deps
%PYTHON% -c "import PIL, webview, pystray" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [INFO] Installing deps...
    %PYTHON% -m pip install -r "%~dp0requirements.txt" -q
)

:: Launch the single HTML/pywebview UI entry point
%PYTHON% "%~dp0webapp.py"
pause
