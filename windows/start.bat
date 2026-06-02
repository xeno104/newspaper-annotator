@echo off
title Newspaper Intelligence Hub
color 0b

echo ==================================================
echo    Newspaper Intelligence Hub is starting...
echo ==================================================
echo.
echo Checking dependencies (this takes a moment on first run)...
pip3 install Flask Pillow requests PyMuPDF --quiet

echo.
echo Launching the server and opening your browser...
echo.
echo NOTE: Keep this black window open while using the app!
echo To quit, simply close this window.
echo.

:: Starts the python server
python app.py

pause