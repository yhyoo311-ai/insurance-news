# -*- coding: utf-8 -*-
"""텔레그램으로 다이제스트 발송."""

import html
from datetime import datetime, timedelta, timezone

import requests

from config import DIGEST_TITLE, TIMEZONE_OFFSET_HOURS

KST = timezone(timedelta(hours=TIMEZONE_OFFSET_HOURS))
TELEGRAM_MAX = 4000  # 안전 여유 (한도 4096)

CATEGORY_ICON = {"생명": "🟦 생명보험", "손해": "🟥 손해보험", "공통": "⬜ 업계 공통"}
CATEGORY_ORDER = ["생명", "손해", "공통"]


def _esc(text: str) -> str:
    return html.escape(text or "")


def build_message(articles: list[dict]) -> str:
    today = datetime.now(KST).strftime("%Y-%m-%d (%a)")
    parts = [f"<b>{_esc(DIGEST_TITLE)}</b>", f"🗓 {today} · 총 {len(articles)}건", ""]

    idx = 1
    for cat in CATEGORY_ORDER:
        group = [a for a in articles if a.get("category") == cat]
        if not group:
            continue
        parts.append(f"<b>{CATEGORY_ICON[cat]}</b>")
        for a in group:
            title = _esc(a["title"])
            summary = _esc(a.get("summary", ""))
            url = _esc(a["url"])
            src = _esc(a.get("source", ""))
            parts.append(f'{idx}. <a href="{url}">{title}</a>')
            parts.append(f"   {summary}")
            if src:
                parts.append(f"   <i>{src}</i>")
            parts.append("")
            idx += 1

    return "\n".join(parts).strip()


def _split(text: str, limit: int = TELEGRAM_MAX) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > limit:
            chunks.append(cur)
            cur = ""
        cur += line + "\n"
    if cur.strip():
        chunks.append(cur)
    return chunks


def send_telegram(message: str, bot_token: str, chat_id: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    for chunk in _split(message):
        resp = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=15,
        )
        if not resp.ok:
            print(f"[notify] 텔레그램 발송 실패: {resp.status_code} {resp.text}")
            resp.raise_for_status()
    print("[notify] 텔레그램 발송 완료")
