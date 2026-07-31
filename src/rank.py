# -*- coding: utf-8 -*-
"""중요도 스코어링 → 섹션별 상위 min~max건 선별 (+ 핀 회사 보장)."""

from datetime import datetime, timedelta, timezone

from config import (
    IMPORTANCE_KEYWORDS,
    PINNED_MAX,
    PINNED_SCORE_BONUS,
    SECTIONS,
    TIMEZONE_OFFSET_HOURS,
)
from src.classify import is_pinned

KST = timezone(timedelta(hours=TIMEZONE_OFFSET_HOURS))


def score(article: dict) -> float:
    """중복 보도량 + 키워드 가중치 + 최신성 + 핀 가산으로 점수화."""
    s = 0.0
    s += (article.get("dup_count", 1) - 1) * 2.0

    title = article["title"]
    for kw, w in IMPORTANCE_KEYWORDS.items():
        if kw in title:
            s += w

    age_h = (datetime.now(KST) - article["published"]).total_seconds() / 3600
    s += max(0.0, 2.0 - age_h / 12.0)

    if is_pinned(article):
        s += PINNED_SCORE_BONUS
    return s


def select_by_sections(articles: list[dict]) -> list[dict]:
    """섹션별로 점수 상위 max건까지 선별. 핀 회사 기사는 최소 1건(최대 PINNED_MAX) 보장."""
    for a in articles:
        a["score"] = score(a)

    selected: list[dict] = []
    chosen_ids: set[int] = set()
    logs: list[str] = []

    for sec in SECTIONS:
        group = sorted(
            [a for a in articles if a.get("section") == sec["name"]],
            key=lambda a: a["score"],
            reverse=True,
        )
        take = group[: sec.get("max", 5)]
        for a in take:
            selected.append(a)
            chosen_ids.add(id(a))
        logs.append(f"{sec['name']} {len(take)}건")

    # 핀 회사 보장: 선택된 것이 없으면 점수 높은 핀 기사를 해당 섹션에 편입
    pinned_pool = sorted(
        [a for a in articles if is_pinned(a)], key=lambda a: a["score"], reverse=True
    )
    pinned_in = sum(1 for a in selected if is_pinned(a))
    need = min(len(pinned_pool), PINNED_MAX) - pinned_in
    added = 0
    for a in pinned_pool:
        if need <= 0:
            break
        if id(a) not in chosen_ids:
            selected.append(a)
            chosen_ids.add(id(a))
            need -= 1
            added += 1
    if added:
        logs.append(f"핀 회사 보장 +{added}건")

    print("[rank] 섹션별 선별 -> " + ", ".join(logs))
    print(f"[rank] 총 {len(selected)}건 선별")
    return selected


# 하위 호환: 기존 이름으로도 호출 가능
def rank_and_select(articles: list[dict], limit: int = None) -> list[dict]:
    return select_by_sections(articles)
