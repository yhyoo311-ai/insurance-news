@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 보험 뉴스 다이제스트 설정 대시보드를 시작합니다...
echo 브라우저가 자동으로 열립니다. (창을 닫으면 대시보드가 종료됩니다)
python dashboard.py
pause
