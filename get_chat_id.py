# -*- coding: utf-8 -*-
"""텔레그램 chat_id 확인용 1회성 도구.

사용법:
  1) BotFather에서 만든 봇을 텔레그램에서 찾아 대화창을 연다.
  2) 봇에게 아무 메시지나 하나 보낸다 (예: "안녕").
  3) TELEGRAM_BOT_TOKEN 을 넣고 이 스크립트를 실행한다.
     python get_chat_id.py <봇토큰>
     (또는 .env에 TELEGRAM_BOT_TOKEN 설정 후 인자 없이 실행)
"""

import os
import sys

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def main() -> None:
    token = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("봇 토큰을 인자로 주거나 .env에 TELEGRAM_BOT_TOKEN을 설정하세요.")
        sys.exit(1)

    resp = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=15)
    data = resp.json()

    if not data.get("ok"):
        print(f"오류: {data}")
        sys.exit(1)

    updates = data.get("result", [])
    if not updates:
        print("업데이트가 없습니다. 봇에게 먼저 메시지를 한 번 보낸 뒤 다시 실행하세요.")
        return

    seen = {}
    for u in updates:
        msg = u.get("message") or u.get("channel_post") or {}
        chat = msg.get("chat", {})
        if chat.get("id"):
            seen[chat["id"]] = chat.get("title") or chat.get("username") or chat.get("first_name", "")

    print("발견된 chat_id:")
    for cid, name in seen.items():
        print(f"  chat_id = {cid}   ({name})")
    print("\n위 chat_id 를 TELEGRAM_CHAT_ID 로 사용하세요.")


if __name__ == "__main__":
    main()
