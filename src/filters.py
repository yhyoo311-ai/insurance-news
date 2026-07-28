# -*- coding: utf-8 -*-
"""노이즈 기사 제거 + 보험업계 관련성 필터.

핀 지정 회사(예: 롯데손해보험) 기사는 어떤 경우에도 제외하지 않는다.
"""

from config import EXCLUDE_KEYWORDS, RELEVANCE_TERMS, REQUIRE_RELEVANCE
from src.classify import is_pinned


def _has_any(text: str, terms: list[str]) -> bool:
    return any(t in text for t in terms)


def filter_articles(articles: list[dict]) -> list[dict]:
    kept: list[dict] = []
    dropped_noise = 0
    dropped_irrelevant = 0

    for a in articles:
        # 핀 지정 회사 기사는 필터를 통과시킨다 (보장 포함 대상)
        if is_pinned(a):
            kept.append(a)
            continue

        text = f"{a['title']} {a.get('description', '')}"

        if _has_any(a["title"], EXCLUDE_KEYWORDS):
            dropped_noise += 1
            continue

        if REQUIRE_RELEVANCE and not _has_any(text, RELEVANCE_TERMS):
            dropped_irrelevant += 1
            continue

        kept.append(a)

    print(
        f"[filter] 노이즈 {dropped_noise} + 비관련 {dropped_irrelevant} 제거 "
        f"→ {len(kept)}건 유지"
    )
    return kept
