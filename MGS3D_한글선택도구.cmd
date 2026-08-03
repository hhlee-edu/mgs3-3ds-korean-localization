@echo off
cd /d "%~dp0"
python tools\mgs3d_codec_review_gui.py
if errorlevel 1 pause
