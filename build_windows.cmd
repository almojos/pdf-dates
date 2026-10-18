@echo off
setlocal
if not defined TMPDIR set "TMPDIR=%LOCALAPPDATA%\PDFDates\cache"
cd /d "%~dp0"
python -m PyInstaller --noconfirm --clean --distpath dist --workpath "%TMPDIR%\pdf-dates-build" "PDF Dates.spec"
if errorlevel 1 exit /b 1
echo Ejecutable creado en dist\PDF Dates.exe
