# -*- coding: utf-8 -*-
"""중요도 스코어링 → 상위 N건 선별 + 핀 지정 회사 보장 포함."""

from datetime import datetime, timedelta, timezone

from config import (
    IMPORTANCE_KEYWORDS,
    MAX_ARTICLES,
    PINNED_MAX,
    PINNED_SCORE_BONUS,
    TIMEZONE_OFFSET_HOURS,
)
from src.classify import is_pinned

KST = timezone(timedelta(hours=TIMEZONE_OFFSET_HOURS))


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


def _select_with_pins(ranked: list[dict], limit: int) -> list[dict]:
    """핀 지정 회사 기사를 '정확히 min(보유수, PINNED_MAX)건' 포함시킨다.
    - 보장(floor): 있으면 반드시 1건 이상 포함
    - 상한(cap): 같은 회사 이슈로 도배되지 않도록 PINNED_MAX건까지만
    나머지 슬롯은 점수 높은 일반 기사로 채운다.
    (ranked는 이미 사건 중복 제거된 풀이라 내용 중복 없음)"""
    pinned_ranked = [a for a in ranked if is_pinned(a)]
    non_pinned_ranked = [a for a in ranked if not is_pinned(a)]

    if not pinned_ranked:
        return ranked[:limit]

    target = min(len(pinned_ranked), PINNED_MAX)
    keep_pinned = pinned_ranked[:target]                 # 점수 높은 핀 기사 우선
    fill = non_pinned_ranked[: max(0, limit - len(keep_pinned))]

    selected = sorted(keep_pinned + fill, key=lambda a: a["score"], reverse=True)
    names = ", ".join(a["title"][:20] for a in keep_pinned)
    print(f"[rank] 핀 지정 회사 기사 {len(keep_pinned)}건 포함(상한 {PINNED_MAX}) → {names}")
    return selected


def rank_and_select(articles: list[dict], limit: int = MAX_ARTICLES) -> list[dict]:
    for a in articles:
        a["score"] = score(a)

    ranked = sorted(articles, key=lambda a: a["score"], reverse=True)
    selected = _select_with_pins(ranked, limit)

    print(f"[rank] {len(articles)}건 중 상위 {len(selected)}건 선별")
    return selected
