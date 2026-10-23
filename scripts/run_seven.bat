@echo off
rem Starts Seven from source. Run from anywhere; it switches to the project root first.
title SEVEN
cd /d "%~dp0.."
call venv\Scripts\activate
python main.py
pause
