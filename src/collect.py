# -*- coding: utf-8 -*-
"""뉴스 수집: 네이버 검색 API + (선택) RSS."""

import html
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import requests

try:
    import feedparser
except ImportError:  # RSS를 안 쓰면 없어도 됨
    feedparser = None

from config import (
    NAVER_SEARCH_QUERIES,
    NAVER_DISPLAY,
    LOOKBACK_HOURS,
    RSS_FEEDS,
    TIMEZONE_OFFSET_HOURS,
)

NAVER_URL = "https://openapi.naver.com/v1/search/news.json"
KST = timezone(timedelta(hours=TIMEZONE_OFFSET_HOURS))


def _clean(text: str) -> str:
    """네이버 응답의 <b> 태그·HTML 엔티티 제거."""
    text = re.sub(r"<[^>]+>", "", text or "")
    return html.unescape(text).strip()


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def _parse_naver_date(s: str) -> datetime:
    # 예: "Mon, 27 Jul 2026 12:00:00 +0900"
    return datetime.strptime(s, "%a, %d %b %Y %H:%M:%S %z")


def collect_naver(client_id: str, client_secret: str) -> list[dict]:
    """네이버 뉴스 검색 API로 최근 기사 수집."""
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    cutoff = datetime.now(KST) - timedelta(hours=LOOKBACK_HOURS)
    articles: list[dict] = []

    for query in NAVER_SEARCH_QUERIES:
        try:
            resp = requests.get(
                NAVER_URL,
                headers=headers,
                params={"query": query, "display": NAVER_DISPLAY, "sort": "date"},
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"[collect] 네이버 요청 실패 (query={query}): {e}")
            continue

        for item in resp.json().get("items", []):
            try:
                published = _parse_naver_date(item["pubDate"])
            except (KeyError, ValueError):
                continue
            if published < cutoff:
                continue

            url = item.get("originallink") or item.get("link", "")
            articles.append(
                {
                    "title": _clean(item.get("title", "")),
                    "url": url,
                    "description": _clean(item.get("description", "")),
                    "published": published,
                    "source": _domain(url) or "naver",
                    "query": query,
                }
            )

    print(f"[collect] 네이버 수집: {len(articles)}건 (쿼리 {len(NAVER_SEARCH_QUERIES)}개)")
    return articles


def collect_rss() -> list[dict]:
    """전문지 RSS 수집 (RSS_FEEDS가 비어 있으면 건너뜀)."""
    if not RSS_FEEDS:
        return []
    if feedparser is None:
        print("[collect] feedparser 미설치 — RSS 건너뜀")
        return []

    cutoff = datetime.now(KST) - timedelta(hours=LOOKBACK_HOURS)
    articles: list[dict] = []

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"[collect] RSS 파싱 실패 ({feed_url}): {e}")
            continue

        for entry in feed.entries:
            published = None
            if getattr(entry, "published_parsed", None):
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).astimezone(KST)
            if published and published < cutoff:
                continue

            url = entry.get("link", "")
            articles.append(
                {
                    "title": _clean(entry.get("title", "")),
                    "url": url,
                    "description": _clean(entry.get("summary", "")),
                    "published": published or datetime.now(KST),
                    "source": _domain(url) or _domain(feed_url),
                    "query": "rss",
                }
            )

    print(f"[collect] RSS 수집: {len(articles)}건")
    return articles


def collect_all(naver_id: str, naver_secret: str) -> list[dict]:
    """모든 소스에서 수집하고 URL 기준 1차 중복 제거."""
    articles = collect_naver(naver_id, naver_secret) + collect_rss()

    seen_urls = set()
    unique = []
    for a in articles:
        key = a["url"] or a["title"]
        if key in seen_urls:
            continue
        seen_urls.add(key)
        unique.append(a)

    print(f"[collect] URL 중복 제거 후: {len(unique)}건")
    return unique
