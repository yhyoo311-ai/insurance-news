@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 업로드용 스냅샷(dist\index.html)을 만듭니다...
echo 시세와 회사별 뉴스를 지금 시점 값으로 구워 넣습니다. (1~3분)
echo.
python build_static.py --open
pause
