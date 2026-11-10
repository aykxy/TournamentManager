@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call run_windows.bat
".venv\Scripts\python.exe" -m pip install pyinstaller
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onedir --windowed --name ArenaTournamentManager --add-data "assets\arena_logo.png;assets" --collect-all PySide6.QtWebEngineWidgets main.py
if errorlevel 1 goto failed
echo Build complete in dist\ArenaTournamentManager
pause
exit /b 0
:failed
echo Build failed.
pause
exit /b 1
