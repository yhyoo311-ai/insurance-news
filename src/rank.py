# -*- coding: utf-8 -*-
"""중요도 스코어링 → 상위 N건 선별."""

from datetime import datetime, timedelta, timezone

from config import IMPORTANCE_KEYWORDS, MAX_ARTICLES, TIMEZONE_OFFSET_HOURS

KST = timezone(timedelta(hours=TIMEZONE_OFFSET_HOURS))


def score(article: dict) -> float:
    """중복 보도량 + 키워드 가중치 + 최신성으로 점수화."""
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

    return s


def rank_and_select(articles: list[dict], limit: int = MAX_ARTICLES) -> list[dict]:
    for a in articles:
        a["score"] = score(a)

    ranked = sorted(articles, key=lambda a: a["score"], reverse=True)
    selected = ranked[:limit]

    print(f"[rank] {len(articles)}건 중 상위 {len(selected)}건 선별")
    return selected
