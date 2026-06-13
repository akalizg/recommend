@echo off
chcp 65001 >nul
title RecipeRecommend - Recommendation System Launcher

set ROOT=%~dp0
cd /d "%ROOT%"

echo.
echo ============================================
echo   RecipeRecommend - Recipe Recommendation System
echo ============================================
echo.

:: ─── 1. Check Python ───────────────────────
echo [1/5] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo         Python %%v OK

:: ─── 2. Install / Verify Dependencies ──────
echo.
echo [2/5] Checking dependencies...
python -c "import faiss; import fastapi; import xgboost; import redis; print('All OK')" >nul 2>&1
if %errorlevel% neq 0 (
    echo         Installing Python packages...
    pip install -r requirements.txt -q
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
)
echo         Dependencies OK

:: Step 3. Check recipe model artifacts
echo.
echo [3/5] Checking model artifacts...

set INDEX_FILE=%ROOT%models\faiss_hnsw.index

if not exist "%INDEX_FILE%" (
    echo         [WARN] FAISS index not found: %INDEX_FILE%
    echo         Generate recipe artifacts before using vector recall.
) else (
    echo         Model artifacts found
)

:: ─── 4. Start Redis ────────────────────────
echo.
echo [4/5] Starting Redis...

:: Check if Redis is already running
redis-cli ping >nul 2>&1
if %errorlevel% equ 0 (
    echo         Redis already running
) else (
    echo         Attempting to start Redis...
    :: Try Docker first
    docker ps >nul 2>&1
    if %errorlevel% equ 0 (
        docker start redis 2>nul || docker run -d -p 6379:6379 --name redis redis:7-alpine
        echo         Redis started via Docker
    ) else (
        echo         [WARN] Redis not available - running without cache
        echo         Install Redis or Docker for caching support
    )
)

:: ─── 5. Start Services ─────────────────────
echo.
echo [5/5] Starting services...

:: Start FastAPI in new window
echo         Starting FastAPI backend...
start "MovieRec-API" cmd /c "cd /d %ROOT% && uvicorn app.main:app --host 0.0.0.0 --port 8000"

:: Wait for API to be ready
echo         Waiting for API to start...
set /a RETRY=0
:wait_api
timeout /t 2 /nobreak >nul
curl -s http://localhost:8000/health >nul 2>&1
if %errorlevel% equ 0 goto api_ready
set /a RETRY+=1
if %RETRY% lss 20 goto wait_api
echo         [WARN] API may not be ready yet
:api_ready
echo         FastAPI: http://localhost:8000
echo         Swagger: http://localhost:8000/docs

:: Start Frontend in new window
echo         Starting Vue3 frontend...
start "MovieRec-Frontend" cmd /c "cd /d %ROOT%frontend && npx vite --host 0.0.0.0 --port 3000"

echo.
echo ============================================
echo   All services started!
echo.
echo   Frontend:  http://localhost:3000
echo   Backend:   http://localhost:8000
echo   API Docs:  http://localhost:8000/docs
echo ============================================
echo.
echo   Close the terminal windows (MovieRec-API,
echo   MovieRec-Frontend) to stop the services.
echo ============================================

pause
