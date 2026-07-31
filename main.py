# -*- coding: utf-8 -*-
"""보험 뉴스 다이제스트 파이프라인 진입점.

로컬 실행:  python main.py
GitHub Actions에서도 동일하게 실행됩니다.
필요한 환경변수: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET,
                 GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()  # 로컬 .env 지원 (Actions에서는 무해)
except ImportError:
    pass

from src import console

console.setup()

from src.collect import collect_all
from src.filters import filter_articles
from src.classify import classify_and_dedup
from src.rank import rank_and_select
from src.summarize import summarize
from src.notify import build_message, send_telegram


REQUIRED = [
    "NAVER_CLIENT_ID",
    "NAVER_CLIENT_SECRET",
    "GEMINI_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
]


def check_env() -> dict:
    env = {k: os.environ.get(k, "") for k in REQUIRED}
    missing = [k for k, v in env.items() if not v]
    if missing:
        print(f"[main] 환경변수 누락: {', '.join(missing)}")
        sys.exit(1)
    return env


def main() -> None:
    env = check_env()

    articles = collect_all(env["NAVER_CLIENT_ID"], env["NAVER_CLIENT_SECRET"])
    if not articles:
        print("[main] 수집된 기사가 없습니다. 종료.")
        return

    articles = filter_articles(articles)
    articles = classify_and_dedup(articles)
    selected = rank_and_select(articles)
    selected = summarize(selected, env["GEMINI_API_KEY"])

    message = build_message(selected)
    send_telegram(message, env["TELEGRAM_BOT_TOKEN"], env["TELEGRAM_CHAT_ID"])
    print("[main] 완료.")


if __name__ == "__main__":
    main()
