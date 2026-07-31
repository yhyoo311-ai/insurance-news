@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo DART 전자공시에서 보험사 재무·주주를 가져옵니다.
echo   자산총계 / 부채총계 / 자본총계 / 영업이익 / 당기순이익 / 보험계약부채 / 최대주주
echo   (K-ICS 비율은 DART에 없어 관리자모드에서 직접 관리합니다)
echo.
echo 먼저 미리보기를 보여준 뒤 반영 여부를 묻습니다. (37개사, 1~2분)
echo.
python sync_dart.py
echo.
set /p YN=반영할까요? (Y/N):
if /i "%YN%"=="Y" python sync_dart.py --write
pause
