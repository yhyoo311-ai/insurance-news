# -*- coding: utf-8 -*-
"""분류(생명/손해/공통) + 같은 사건 중복 제거."""

import re
from difflib import SequenceMatcher

from config import (
    LIFE_INSURERS,
    NONLIFE_INSURERS,
    LIFE_KEYWORDS,
    NONLIFE_KEYWORDS,
    DEDUP_SIMILARITY,
    PINNED_COMPANIES,
    SECTIONS,
)


def is_pinned(article: dict) -> bool:
    """핀 지정 회사(예: 롯데손해보험) 기사인지 여부."""
    text = f"{article['title']} {article.get('description', '')}"
    return any(c in text for c in PINNED_COMPANIES)


def assign_section(article: dict) -> str:
    """기사를 대구분 섹션 하나에 배정.
    ① 제목에서 섹션 키워드 매칭(정확도↑) → ② 본문 보조 매칭 → ③ 기타(빈 terms) 수용."""
    title = article["title"]
    text = f"{title} {article.get('description', '')}"

    for sec in SECTIONS:
        if sec.get("terms") and any(t in title for t in sec["terms"]):
            return sec["name"]
    for sec in SECTIONS:
        if sec.get("terms") and any(t in text for t in sec["terms"]):
            return sec["name"]
    for sec in SECTIONS:
        if not sec.get("terms"):
            return sec["name"]
    return SECTIONS[-1]["name"] if SECTIONS else "기타"


def _match_count(text: str, terms: list[str]) -> int:
    return sum(1 for t in terms if t in text)


def classify_one(article: dict) -> str:
    """기사 하나를 '생명' / '손해' / '공통' 으로 분류."""
    text = f"{article['title']} {article['description']}"

    life_score = _match_count(text, LIFE_INSURERS) * 2 + _match_count(text, LIFE_KEYWORDS)
    nonlife_score = _match_count(text, NONLIFE_INSURERS) * 2 + _match_count(text, NONLIFE_KEYWORDS)

    if life_score == 0 and nonlife_score == 0:
        return "공통"
    if life_score > nonlife_score:
        return "생명"
    if nonlife_score > life_score:
        return "손해"
    return "공통"  # 동점(생손보 모두 언급)


def _normalize(title: str) -> str:
    """유사도 비교용: 공백·기호 제거."""
    return re.sub(r"[^\w가-힣]", "", title)


def dedup_by_similarity(articles: list[dict]) -> list[dict]:
    """제목 유사도가 높은 기사를 같은 사건으로 묶어 대표 1건만 남김.
    묶인 기사 수는 dup_count 로 저장(중요도 스코어링에 사용)."""
    kept: list[dict] = []

    for article in articles:
        norm = _normalize(article["title"])
        matched = None
        for k in kept:
            if SequenceMatcher(None, norm, k["_norm"]).ratio() >= DEDUP_SIMILARITY:
                matched = k
                break

        if matched:
            matched["dup_count"] += 1
            # 더 이른 시각(원 보도)을 대표로 유지
            if article["published"] < matched["published"]:
                matched.update(
                    title=article["title"],
                    url=article["url"],
                    description=article["description"],
                    published=article["published"],
                    source=article["source"],
                    _norm=norm,
                )
        else:
            article["dup_count"] = 1
            article["_norm"] = norm
            kept.append(article)

    print(f"[classify] 사건 중복 제거: {len(articles)} → {len(kept)}건")
    return kept


def classify_and_dedup(articles: list[dict]) -> list[dict]:
    for a in articles:
        a["category"] = classify_one(a)      # 생명 / 손해 / 공통 (인라인 태그용)
        a["section"] = assign_section(a)      # 대구분 섹션
    return dedup_by_similarity(articles)
