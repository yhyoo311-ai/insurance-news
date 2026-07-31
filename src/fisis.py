# -*- coding: utf-8 -*-
"""FISIS(금융감독원 금융통계정보시스템) OpenAPI — 업무보고서 기반 감독통계.

DART 와 무엇이 다른가
  DART 는 **증권을 발행한 회사**가 내는 사업보고서를 모읍니다. 그래서 증권 미발행
  보험사(라이나·메트라이프·AIA·카카오페이손보 등)는 재무가 아예 없습니다.
  FISIS 는 보험사가 **감독당국에 매분기 내는 업무보고서**에서 뽑은 값이라
  상장·비상장을 가리지 않습니다. DART 로 못 채운 회사가 여기서 채워집니다.

이 모듈이 채우는 값
  · K-ICS(지급여력비율) — DART 재무제표에 없는 감독지표. 이것이 주목적입니다.
  · 자산총계 · 부채총계 · 자본총계 · 영업이익 · 당기순이익 · 보험계약부채

교차 검증
  삼성생명 2025.12 자산총계가 DART 값(3,099,483억원)과 원 단위까지 일치합니다.
  같은 회사를 두 출처로 조회해 어긋나면 어느 쪽이든 의심해야 한다는 뜻이기도 합니다.

경과조치
  K-ICS 는 '경과조치 적용 전/후' 두 값이 옵니다. 경과조치를 신청하지 않은 회사는
  '적용 후'가 0 으로 오므로, **적용 후가 0 보다 크면 그 값을, 아니면 적용 전**을 쓰고
  어느 쪽을 썼는지 kics_basis 에 남깁니다. 금감원 보도자료의 업계 수치도 적용 후 기준입니다.

인증키: 환경변수 FISIS_API_KEY (https://fisis.fss.or.kr 에서 무료 발급)
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://fisis.fss.or.kr/openapi/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

LIFE, NONLIFE = "H", "I"

# 권역별 통계표 번호. 2023.3월 이후 IFRS17 서식이라 그 이전 표(SH003 등)와 다릅니다.
TABLES = {
    LIFE:    {"assets": "SH150", "liabilities": "SH151", "income": "SH154", "capital": "SH021"},
    NONLIFE: {"assets": "SI146", "liabilities": "SI147", "income": "SI150", "capital": "SI021"},
}

# 계정은 코드가 아니라 이름으로 고릅니다. 서식이 개정되면 코드는 밀리지만
# 이름은 남기 때문입니다 (SH151 의 자본총계가 F 인 것에 기대지 않습니다).
FIELDS = {
    "assets":                ("assets",      lambda n: n == "자산총계"),
    "liabilities":           ("liabilities", lambda n: n == "부채총계"),
    "equity":                ("liabilities", lambda n: n == "자본총계"),
    "insurance_liabilities": ("liabilities", lambda n: n.strip("()") == "보험계약부채"),
    "operating_income":      ("income",      lambda n: n.startswith("영업이익")),
    "net_income":            ("income",      lambda n: n.startswith("당기순이익")),
}

MIN_INTERVAL = 0.2
MAX_RETRY = 3
_throttle = threading.Lock()
_last_call = [0.0]

WON_PER_EOK = 100_000_000  # FISIS 는 원 단위로 줍니다. insurers.json 은 억원입니다.


class FisisError(RuntimeError):
    pass


def api_key() -> str:
    key = os.environ.get("FISIS_API_KEY", "").strip()
    if not key:
        raise FisisError(
            "FISIS_API_KEY 가 없습니다. .env 에 추가하세요 "
            "(https://fisis.fss.or.kr → 인증키 신청)."
        )
    return key


def call(endpoint: str, **params) -> dict:
    """FISIS 호출. err_cd 가 000 이 아니면 예외로 올립니다."""
    q = urllib.parse.urlencode({"lang": "kr", "auth": api_key(), **params})
    url = f"{BASE}{endpoint}.json?{q}"

    last = None
    for attempt in range(MAX_RETRY):
        with _throttle:
            wait = MIN_INTERVAL - (time.time() - _last_call[0])
            if wait > 0:
                time.sleep(wait)
            _last_call[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            break
        except (urllib.error.URLError, OSError, ValueError) as e:
            last = e
            if attempt == MAX_RETRY - 1:
                raise FisisError(f"{endpoint} 호출 실패: {e}") from e
            time.sleep(0.8 * (attempt + 1))
    else:  # pragma: no cover
        raise FisisError(f"{endpoint} 호출 실패: {last}")

    result = body.get("result") or {}
    code = str(result.get("err_cd") or "")
    if code and code != "000":
        raise FisisError(f"{endpoint} 오류 {code}: {result.get('err_msg')}")
    return result


def companies(part: str) -> list[dict]:
    """권역의 회사 목록. 폐업([폐])도 그대로 돌려주니 호출부에서 거릅니다."""
    return call("companySearch", partDiv=part).get("list") or []


def _rows(finance_cd: str, list_no: str, base_mm: str) -> dict:
    """통계표 한 장을 {계정명: 값(float)} 으로."""
    res = call(
        "statisticsInfoSearch",
        financeCd=finance_cd, listNo=list_no, term="Q",
        startBaseMm=base_mm, endBaseMm=base_mm,
    )
    out = {}
    for row in res.get("list") or []:
        name = (row.get("account_nm") or "").strip()
        raw = row.get("a")
        if not name or raw in (None, ""):
            continue
        try:
            out[name] = float(raw)
        except (TypeError, ValueError):
            continue
    return out


def to_eok(won) -> int | None:
    """원 → 억원 (insurers.json 단위)."""
    if won is None:
        return None
    return int(round(won / WON_PER_EOK))


def kics(finance_cd: str, part: str, base_mm: str) -> tuple[float | None, str]:
    """(지급여력비율, 기준설명). 경과조치 적용 후가 있으면 그것을 씁니다."""
    rows = _rows(finance_cd, TABLES[part]["capital"], base_mm)
    pre = post = None
    for name, value in rows.items():
        if name.startswith("지급여력비율(경과조치 적용 전)"):
            pre = value
        elif name.startswith("지급여력비율(경과조치 적용 후)"):
            post = value

    if post is not None and post > 0:
        return round(post, 2), "경과조치 적용 후"
    if pre is not None:
        # 적용 전 값이 음수면 완전자본잠식입니다. 감추지 않고 그대로 전달합니다.
        return round(pre, 2), "경과조치 적용 전"
    return None, ""


def year_quarters(base_mm: str) -> list[str]:
    """해당 연도의 4개 분기말. 손익은 분기 단독값이라 연간은 합산해야 합니다."""
    year = base_mm[:4]
    return [f"{year}{q}" for q in ("03", "06", "09", "12")]


def snapshot(finance_cd: str, part: str, base_mm: str) -> dict:
    """K-ICS + 재무 한 벌. 없는 항목은 None 으로 남기고 채우지 않습니다.

    재무상태표(자산·부채·자본)는 시점 값이므로 base_mm 한 번만 읽습니다.
    손익계산서는 **분기 단독** 값이라 연간을 만들려면 4개 분기를 더해야 합니다.
    (삼성화재 2025: 5,556+3,982+5,093+2,277=16,908억, DART 연간 16,909억과 일치)
    """
    if part not in TABLES:
        raise FisisError(f"알 수 없는 권역: {part}")

    ratio, basis = kics(finance_cd, part, base_mm)
    out = {"kics": ratio, "kics_basis": basis, "base_month": base_mm}

    cache: dict[str, dict] = {}

    def rows(list_no: str, mm: str) -> dict:
        if (list_no, mm) not in cache:
            cache[(list_no, mm)] = _rows(finance_cd, list_no, mm)
        return cache[(list_no, mm)]

    for field, (table, match) in FIELDS.items():
        list_no = TABLES[part][table]

        if table != "income":
            hit = next((v for n, v in rows(list_no, base_mm).items() if match(n)), None)
            out[field] = to_eok(hit)
            continue

        # 연간 손익 = 4개 분기 합. 한 분기라도 비면 합계가 과소평가되므로
        # 채우지 않고 None 으로 둡니다 (반쪽 숫자를 연간값처럼 보이게 하지 않기).
        parts, missing = [], False
        for mm in year_quarters(base_mm):
            hit = next((v for n, v in rows(list_no, mm).items() if match(n)), None)
            if hit is None:
                missing = True
                break
            parts.append(hit)
        out[field] = None if missing else to_eok(sum(parts))

    out["income_quarters"] = year_quarters(base_mm)
    return out
