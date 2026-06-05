@echo off
chcp 65001 >nul
title MovieRec - Stopping Services

echo.
echo ============================================
echo   Stopping MovieRec services...
echo ============================================
echo.

:: Kill FastAPI
echo Stopping FastAPI...
taskkill /fi "WINDOWTITLE eq MovieRec-API*" /f >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING" 2^>nul') do (
    taskkill /f /pid %%a >nul 2>&1
)
echo         FastAPI stopped

:: Kill Frontend
echo Stopping Frontend...
taskkill /fi "WINDOWTITLE eq MovieRec-Frontend*" /f >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000.*LISTENING" 2^>nul') do (
    taskkill /f /pid %%a >nul 2>&1
)
echo         Frontend stopped

:: Optionally stop Redis
set /p STOP_REDIS="Stop Redis? (y/n, default n): "
if /i "%STOP_REDIS%"=="y" (
    docker stop redis >nul 2>&1 && echo Redis stopped || echo Redis not managed by Docker
)

echo.
echo ============================================
echo   All services stopped.
echo ============================================
echo.

pause
