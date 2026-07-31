# -*- coding: utf-8 -*-
"""시세·재무 조회 (Yahoo Finance).

신뢰 구간을 명확히 나눕니다.
  · Yahoo 실시간   : 현재가, 전일대비, 통화, 시가총액, 52주 고/저, 주가 시계열
  · data/insurers.json : 총자산, 자본, 순이익, K-ICS, 주주  (관리자모드에서 수정)
  · 파생 계산      : PER·PBR·ROE = 시가총액/순이익, 시가총액/자본, 순이익/자본

API 키가 필요 없습니다. 응답은 디스크에 캐시해 반복 조회를 줄입니다.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache")
CACHE_TTL = 15 * 60  # 15분
CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# 차트에 표시할 거래일 수
CHART_DAYS = 60


# ─────────────────────── 캐시 ───────────────────────

def _cache_path(key: str) -> str:
    safe = key.replace("/", "_").replace("\\", "_").replace("=", "_")
    return os.path.join(CACHE_DIR, f"{safe}.json")


def _cache_get(key: str):
    path = _cache_path(key)
    try:
        if time.time() - os.path.getmtime(path) > CACHE_TTL:
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _cache_put(key: str, value) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        with open(_cache_path(key), "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False)
    except OSError:
        pass


# ─────────────────────── Yahoo 조회 ───────────────────────

MAX_RETRY = 3


def _get_json(url: str, timeout: int = 15):
    """Yahoo 조회 1회. 429/5xx 는 백오프 재시도합니다.

    로컬에서는 15분 캐시가 대부분을 막아주지만, GitHub Actions 는 매 실행이
    새 컨테이너라 캐시가 없습니다. 하루 16회 빌드가 매번 40여 건을 새로 조회하므로
    재시도가 없으면 간헐적으로 '시세 조회 실패' 가 섞여 배포됩니다.
    """
    for attempt in range(MAX_RETRY):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == MAX_RETRY - 1:
                raise
            time.sleep(1.5 * (2 ** attempt))
        except (urllib.error.URLError, OSError):
            if attempt == MAX_RETRY - 1:
                raise
            time.sleep(1.0 * (2 ** attempt))
    raise urllib.error.URLError("retry exhausted")


def fetch_chart(ticker: str, days: int = CHART_DAYS) -> dict | None:
    """주가 시계열 + 메타. 실패하면 None (호출부에서 '조회 실패'로 표시)."""
    cached = _cache_get(f"chart_{ticker}_{days}")
    if cached is not None:
        return cached

    # 60거래일을 확보하려면 달력일 기준으로 넉넉히 받아야 합니다.
    rng = "6mo" if days <= 110 else "1y"
    try:
        data = _get_json(f"{CHART_URL.format(sym=ticker)}?range={rng}&interval=1d")
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"[market] {ticker} 차트 조회 실패: {type(e).__name__}")
        return None

    chart = data.get("chart") or {}
    if chart.get("error") or not chart.get("result"):
        print(f"[market] {ticker} 응답 오류: {chart.get('error')}")
        return None

    res = chart["result"][0]
    meta = res.get("meta") or {}
    stamps = res.get("timestamp") or []
    closes = ((res.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []

    # 휴장일(None)을 걸러낸 뒤 마지막 days개만 사용
    series = [
        {"t": t, "c": round(float(c), 2)}
        for t, c in zip(stamps, closes)
        if c is not None
    ][-days:]

    if len(series) < 2:
        print(f"[market] {ticker} 유효 종가 부족 ({len(series)}건)")
        return None

    last = series[-1]["c"]
    prev = series[-2]["c"]
    out = {
        "ticker": ticker,
        "name_yahoo": meta.get("longName") or meta.get("shortName") or "",
        "currency": meta.get("currency") or "KRW",
        "exchange": meta.get("fullExchangeName") or meta.get("exchangeName") or "",
        "price": meta.get("regularMarketPrice") or last,
        "prev_close": prev,
        "change_pct": round((last - prev) / prev * 100, 2) if prev else None,
        "high_52w": meta.get("fiftyTwoWeekHigh"),
        "low_52w": meta.get("fiftyTwoWeekLow"),
        "series": series,
        "series_min": min(p["c"] for p in series),
        "series_max": max(p["c"] for p in series),
    }
    _cache_put(f"chart_{ticker}_{days}", out)
    return out


def fetch_market_cap(ticker: str) -> float | None:
    """시가총액. yfinance 가 있으면 사용하고, 없으면 None."""
    cached = _cache_get(f"mcap_{ticker}")
    if cached is not None:
        return cached.get("v")

    value = None
    try:
        import yfinance as yf

        fast = yf.Ticker(ticker).fast_info
        value = fast.get("marketCap")
    except Exception as e:  # yfinance 미설치·네트워크·스키마 변경 모두 흡수
        print(f"[market] {ticker} 시가총액 조회 실패: {type(e).__name__}")

    _cache_put(f"mcap_{ticker}", {"v": value})
    return value


def fetch_usdkrw() -> float | None:
    """USD/KRW 환율 (통화 토글용)."""
    cached = _cache_get("fx_usdkrw")
    if cached is not None:
        return cached.get("v")

    value = None
    try:
        data = _get_json(f"{CHART_URL.format(sym='KRW=X')}?range=5d&interval=1d")
        value = (data["chart"]["result"][0]["meta"] or {}).get("regularMarketPrice")
    except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError, TypeError) as e:
        print(f"[market] 환율 조회 실패: {type(e).__name__}")

    _cache_put("fx_usdkrw", {"v": value})
    return value


# ─────────────────────── 파생 지표 ───────────────────────

EOK = 100_000_000  # 1억원


def derive_ratios(market_cap: float | None, company: dict) -> dict:
    """PER·PBR·ROE 추정. 분모가 0 이하면 산출하지 않습니다(적자·결손)."""
    net_income = (company.get("net_income") or 0) * EOK
    equity = (company.get("equity") or 0) * EOK

    per = round(market_cap / net_income, 1) if market_cap and net_income > 0 else None
    pbr = round(market_cap / equity, 2) if market_cap and equity > 0 else None
    roe = round(net_income / equity * 100, 1) if equity > 0 else None
    return {"per": per, "pbr": pbr, "roe": roe}


def enrich(company: dict) -> dict:
    """회사 1건에 시세·파생지표를 붙인 사본을 반환."""
    out = dict(company)
    ticker = company.get("ticker")
    quote = fetch_chart(ticker) if ticker else None
    market_cap = fetch_market_cap(ticker) if ticker else None

    out["quote"] = quote
    out["market_cap"] = market_cap
    out["ratios"] = derive_ratios(market_cap, company)
    out["change_pct"] = quote["change_pct"] if quote else None
    out["quote_failed"] = bool(ticker) and quote is None

    # 비상장이지만 상장 모회사가 있으면 참고용 지주 시세를 함께 제공
    proxy = company.get("proxy_ticker")
    out["proxy_quote"] = fetch_chart(proxy) if (proxy and not ticker) else None
    return out
