@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 한국 보험사 정보 시스템을 시작합니다...
echo.
echo   히트맵          http://127.0.0.1:5000
echo   관리자모드      http://127.0.0.1:5000/admin/news
echo.
echo 브라우저가 자동으로 열립니다. (이 창을 닫으면 종료됩니다)
python webapp.py
pause
