# -*- coding: utf-8 -*-
"""Google Gemini 무료 API로 기사별 2~3문장 요약 (REST, 별도 패키지 불필요)."""

import json
import re

import requests

from config import SUMMARY_MODEL, SUMMARY_MAX_TOKENS

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM_PROMPT = (
    "너는 국내 보험업계 전문 애널리스트다. 주어진 기사 목록을 읽고 각 기사를 "
    "한국어로 2~3문장으로 요약한다. 핵심 사실(주체·수치·당국 동향 등)을 담고, "
    "추측이나 과장 없이 담백하게 쓴다."
)


def _build_prompt(articles: list[dict]) -> str:
    lines = [
        "다음 기사들을 각각 2~3문장으로 요약해라.",
        "반드시 아래 형식의 JSON 배열만 출력한다:",
        '[{"id": 0, "summary": "..."}, ...]',
        "",
        "기사 목록:",
    ]
    for i, a in enumerate(articles):
        lines.append(f"[{i}] 제목: {a['title']}")
        if a.get("description"):
            lines.append(f"    내용: {a['description']}")
    return "\n".join(lines)


def _extract_json(text: str) -> list[dict]:
    """모델 출력에서 JSON 배열을 안전하게 추출."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def summarize(articles: list[dict], api_key: str) -> list[dict]:
    """각 article에 'summary' 필드를 채워 반환. 실패 시 description으로 대체."""
    if not articles:
        return articles

    url = GEMINI_URL.format(model=SUMMARY_MODEL)
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": _build_prompt(articles)}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": SUMMARY_MAX_TOKENS,
            "responseMimeType": "application/json",  # JSON 출력 강제
            "thinkingConfig": {"thinkingBudget": 0},  # 요약엔 사고 과정 불필요 → 토큰 절약·안정화
        },
    }

    summaries = {}
    try:
        resp = requests.post(
            url,
            params={"key": api_key},
            json=body,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data["candidates"][0]["content"]["parts"][0]["text"]
        summaries = {item["id"]: item["summary"] for item in _extract_json(raw)}
    except Exception as e:
        print(f"[summarize] Gemini 요약 실패, description으로 대체: {e}")

    for i, a in enumerate(articles):
        a["summary"] = summaries.get(i) or a.get("description") or a["title"]

    print(f"[summarize] {len(articles)}건 요약 완료 (성공 {len(summaries)}건)")
    return articles
