# -*- coding: utf-8 -*-
"""중요도 스코어링 → 선별.
보장 규칙: ① 핀 지정 회사(상한/하한) ② 주제 비중(최소 보장) ③ 나머지는 점수순."""

from datetime import datetime, timedelta, timezone

from config import (
    IMPORTANCE_KEYWORDS,
    MAX_ARTICLES,
    PINNED_MAX,
    PINNED_SCORE_BONUS,
    TOPIC_QUOTAS,
    TIMEZONE_OFFSET_HOURS,
)
from src.classify import is_pinned

KST = timezone(timedelta(hours=TIMEZONE_OFFSET_HOURS))


def _matches(article: dict, terms: list[str]) -> bool:
    text = f"{article['title']} {article.get('description', '')}"
    return any(t in text for t in terms)


def _matches_title(article: dict, terms: list[str]) -> bool:
    """주제 비중 보장용: 제목에 주제어가 있는 '진짜 그 주제' 기사만 인정.
    (본문에 스쳐 언급된 실적 기사 등이 쿼터를 채우는 것을 방지)"""
    return any(t in article["title"] for t in terms)


def score(article: dict) -> float:
    """중복 보도량 + 키워드 가중치 + 최신성 + 핀 가산으로 점수화."""
    s = 0.0

    # 여러 매체가 함께 보도 = 그만큼 중요한 사건
    s += (article.get("dup_count", 1) - 1) * 2.0

    # 제목 키워드 가중치
    title = article["title"]
    for kw, w in IMPORTANCE_KEYWORDS.items():
        if kw in title:
            s += w

    # 최신성: 최근일수록 가산 (24h 기준 0~2점)
    age_h = (datetime.now(KST) - article["published"]).total_seconds() / 3600
    s += max(0.0, 2.0 - age_h / 12.0)

    # 핀 지정 회사(예: 롯데손해보험) 소폭 가산
    if is_pinned(article):
        s += PINNED_SCORE_BONUS

    return s


def _select_with_guarantees(ranked: list[dict], limit: int) -> list[dict]:
    """점수 내림차순 ranked에서 보장 규칙을 적용해 최대 limit건 선별.
    (ranked는 이미 사건 중복 제거된 풀이라 내용 중복 없음)"""
    chosen: list[dict] = []
    chosen_ids: set[int] = set()

    def add(a: dict) -> bool:
        if id(a) not in chosen_ids and len(chosen) < limit:
            chosen.append(a)
            chosen_ids.add(id(a))
            return True
        return False

    logs: list[str] = []

    # ① 핀 지정 회사: min(보유, PINNED_MAX)건 (상한/하한)
    pinned = [a for a in ranked if is_pinned(a)]
    pin_target = min(len(pinned), PINNED_MAX)
    for a in pinned[:pin_target]:
        add(a)
    if pinned:
        logs.append(f"핀 회사 {pin_target}건")

    # ② 주제 비중: 주제별 최소 min건 보장 (제목 기준, 점수 높은 것 우선)
    for q in TOPIC_QUOTAS:
        matches = [a for a in ranked if _matches_title(a, q["terms"])]
        have = sum(1 for a in chosen if _matches_title(a, q["terms"]))
        target = min(q["min"], len(matches))
        need = target - have
        for a in matches:
            if need <= 0:
                break
            if id(a) not in chosen_ids and add(a):
                need -= 1
        got = sum(1 for a in chosen if _matches_title(a, q["terms"]))
        logs.append(f"'{q['name']}' {got}건")

    # ③ 나머지는 점수순으로 채움 (핀 회사는 상한 유지 위해 추가 안 함)
    for a in ranked:
        if len(chosen) >= limit:
            break
        if is_pinned(a) and id(a) not in chosen_ids:
            continue
        add(a)

    print("[rank] 보장 적용 → " + ", ".join(logs))
    return sorted(chosen, key=lambda a: a["score"], reverse=True)


def rank_and_select(articles: list[dict], limit: int = MAX_ARTICLES) -> list[dict]:
    for a in articles:
        a["score"] = score(a)

    ranked = sorted(articles, key=lambda a: a["score"], reverse=True)
    selected = _select_with_guarantees(ranked, limit)

    print(f"[rank] {len(articles)}건 중 상위 {len(selected)}건 선별")
    return selected
