@echo off
echo ===== Installing Backend =====
cd backend
py -3 -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt -q
cd ..

echo ===== Installing Frontend =====
cd frontend
call npm install
cd ..

echo ===== Setup Complete =====
echo.
echo Next steps:
echo 1. Run: run_backend.bat (in one terminal)
echo 2. Run: run_frontend.bat (in another terminal)
echo 3. Open: http://localhost:5173
pause
