# -*- coding: utf-8 -*-
"""텔레그램으로 다이제스트 발송 (대구분 섹션별 정리)."""

import html
from datetime import datetime, timedelta, timezone

import requests

from config import DIGEST_TITLE, SECTIONS, TIMEZONE_OFFSET_HOURS

KST = timezone(timedelta(hours=TIMEZONE_OFFSET_HOURS))
TELEGRAM_MAX = 4000  # 안전 여유 (한도 4096)


def _esc(text: str) -> str:
    return html.escape(text or "")


def _section_icon(name: str) -> str:
    table = {
        "M&A": "🤝", "지배구조": "🤝",
        "소비자": "⚖️", "분쟁": "⚖️", "제재": "⚖️",
        "규제": "🏛", "제도": "🏛", "정책": "🏛",
        "실적": "📈", "재무": "📈", "건전성": "📈",
        "상품": "🛍", "영업": "🛍", "채널": "🛍", "GA": "🛍",
        "해외": "🌐", "일반동향": "🌐",
    }
    for key, icon in table.items():
        if key in name:
            return icon
    return "🔹"


def build_message(articles: list[dict]) -> str:
    today = datetime.now(KST).strftime("%Y-%m-%d (%a)")
    parts = [f"<b>{_esc(DIGEST_TITLE)}</b>", f"🗓 {today} · 총 {len(articles)}건", ""]

    idx = 1
    for sec in SECTIONS:
        group = sorted(
            [a for a in articles if a.get("section") == sec["name"]],
            key=lambda a: a.get("score", 0),
            reverse=True,
        )
        if not group:
            continue
        parts.append(f"<b>{_section_icon(sec['name'])} {_esc(sec['name'])}</b>")
        for a in group:
            cat = a.get("category")
            tag = f"[{cat}] " if cat in ("생명", "손해") else ""
            title = _esc(a["title"])
            summary = _esc(a.get("summary", ""))
            url = _esc(a["url"])
            src = _esc(a.get("source", ""))
            parts.append(f'{idx}. {tag}<a href="{url}">{title}</a>')
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
    """chat_id는 콤마로 여러 대상을 지정할 수 있다.
    예) '1111317413,@insurance_daily_kr' → 개인 채팅 + 공개 채널 동시 발송."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    targets = [c.strip() for c in str(chat_id).split(",") if c.strip()]

    failures = []
    for target in targets:
        try:
            for chunk in _split(message):
                resp = requests.post(
                    url,
                    json={
                        "chat_id": target,
                        "text": chunk,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                    timeout=15,
                )
                if not resp.ok:
                    raise RuntimeError(f"{resp.status_code} {resp.text}")
            print(f"[notify] 발송 완료 → {target}")
        except Exception as e:
            print(f"[notify] 발송 실패 → {target}: {e}")
            failures.append(target)

    if failures:
        raise RuntimeError(f"일부 대상 발송 실패: {', '.join(failures)}")
