@echo off
echo ====================================================
echo   Sarthi AI Banking Platform
echo ====================================================
echo.

REM FIX L-8: startup flags now match the production config in main.py __main__.
REM - --reload is for development only (hot-reload on code changes)
REM - --workers is omitted here because --reload is incompatible with multi-worker mode
REM   Use "uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4" for production

echo [1/2] Starting Backend (FastAPI / uvicorn)...
start "Sarthi Backend" cmd /k "cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload --log-level info"

echo [2/2] Starting Frontend (React + Vite)...
start "Sarthi Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo Both services starting in separate windows.
echo   Backend  : http://localhost:8000
echo   Frontend : http://localhost:3000
echo   Swagger  : http://localhost:8000/docs
echo.
echo NOTE: Set SARTHI_API_TOKEN and SARTHI_SUPERVISOR_TOKEN in backend/.env
echo       before running in production.
echo.
pause
