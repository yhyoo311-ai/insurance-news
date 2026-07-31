# -*- coding: utf-8 -*-
"""윈도우 콘솔 출력 안전장치.

한국어 윈도우의 기본 콘솔 코드페이지는 cp949 입니다. cp949 에 없는 문자를
(em dash '—', 화살표 '→' 등) print 하면 UnicodeEncodeError 로 **프로그램이
죽습니다.** 실제로 add_dart_codes.py 가 마지막 줄의 '—' 때문에 죽었습니다.

콘솔 인코딩은 그대로 두고(cp949 콘솔에서 한글이 제대로 보이도록) 인코딩할 수
없는 문자만 '?' 로 대체하게 바꿉니다. .bat 파일들은 chcp 65001 로 UTF-8 을
쓰므로 그쪽에서는 애초에 문제가 없습니다.
"""

import sys


def setup() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, OSError, ValueError):
            pass  # 파이프·리다이렉트 등 reconfigure 가 불가한 경우는 그냥 넘어갑니다
