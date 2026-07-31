# -*- coding: utf-8 -*-
"""(구) 설정 대시보드 → 정보사이트 관리자모드로 옮겨졌습니다.

이 파일은 기존 실행 방식(python dashboard.py / 대시보드_실행.bat)을 그대로
쓰던 사람을 위한 얇은 진입점입니다. 실행하면 정보사이트를 띄우고
관리자모드의 '뉴스·텔레그램 설정' 화면을 곧바로 엽니다.

새 진입점:  python webapp.py    (또는 정보사이트_실행.bat)
"""

import webbrowser
from threading import Timer

from webapp import app

if __name__ == "__main__":
    print("설정 화면은 정보사이트 관리자모드로 통합되었습니다.")
    print("  · 정보사이트     http://127.0.0.1:5000")
    print("  · 뉴스·텔레그램  http://127.0.0.1:5000/admin/news")
    Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000/admin/news")).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
