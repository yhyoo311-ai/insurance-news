# -*- coding: utf-8 -*-
"""DART 전자공시 OpenAPI — 재무·주주 실제 공시값.

이 모듈이 채우는 값 (Yahoo Finance 가 못 주는 것들)
  · 자산총계 · 부채총계 · 자본총계 · 당기순이익 · 영업이익 · 보험계약부채
  · 최대주주 및 특수관계인 지분 (+ 상장사는 5% 이상 대량보유자)

핵심 — **비상장 보험사도 사업보고서를 제출하므로 37개사 전부 조회됩니다.**
교보생명·신한라이프·KB손해보험·메리츠화재 같은 비상장사가 여기서 채워집니다.

연결(CFS) / 별도(OFS)
  보험업계 규모 비교 관행은 별도 기준이라 **별도 우선, 없으면 연결**로 쓰고
  어느 기준을 썼는지 `fs_basis` 에 남깁니다 (섞어 쓰면서 침묵하지 않기 위해).

K-ICS 비율은 DART 재무제표에 없습니다 (금감원·각사 경영공시 항목).
그래서 K-ICS 는 관리자모드에서 손으로 넣는 값으로 남습니다.

인증키: 환경변수 DART_API_KEY (https://opendart.fss.or.kr 에서 무료 발급)
"""

from __future__ import annotations

import io
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(APP_DIR, ".cache")
CORPCODE_PATH = os.path.join(CACHE_DIR, "dart_corpcode.xml")
CORPCODE_TTL = 7 * 24 * 3600  # 회사 목록은 자주 안 바뀜

BASE = "https://opendart.fss.or.kr/api/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# 사업보고서 = 11011 (1분기 11013 · 반기 11012 · 3분기 11014)
ANNUAL = "11011"

# DART 는 분당 호출을 제한합니다. 37개사 × 3요청을 한 번에 던지지 않도록 간격을 둡니다.
MIN_INTERVAL = 0.25
MAX_RETRY = 3
_throttle = threading.Lock()
_last_call = [0.0]

EOK = 100_000_000  # 1억원 — insurers.json 의 금액 단위


class DartError(RuntimeError):
    pass


def api_key() -> str:
    key = os.environ.get("DART_API_KEY", "").strip()
    if not key:
        raise DartError(
            "DART_API_KEY 가 없습니다. .env 에 추가하세요 "
            "(https://opendart.fss.or.kr → 인증키 신청/관리)."
        )
    return key


# ─────────────────────── 호출 ───────────────────────

def _request(path: str, **params) -> bytes:
    params["crtfc_key"] = api_key()
    url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"

    for attempt in range(MAX_RETRY):
        with _throttle:
            wait = MIN_INTERVAL - (time.monotonic() - _last_call[0])
            if wait > 0:
                time.sleep(wait)
            _last_call[0] = time.monotonic()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == MAX_RETRY - 1:
                raise DartError(f"DART HTTP {e.code}") from e
            time.sleep(0.8 * (2 ** attempt))
        except (urllib.error.URLError, OSError) as e:
            if attempt == MAX_RETRY - 1:
                raise DartError(f"DART 연결 실패: {type(e).__name__}") from e
            time.sleep(0.5 * (2 ** attempt))
    raise DartError("DART 요청 실패")


def _get_json(path: str, **params) -> dict:
    """status 코드를 해석해 돌려줍니다.

    000 정상 · 013 조회 데이터 없음 · 020 사용한도 초과 · 100 잘못된 인자
    · 800 시스템 점검 · 900 정의되지 않은 오류 · 901 인증키 오류
    """
    data = json.loads(_request(path, **params))
    status = data.get("status")
    if status == "000":
        return data
    if status == "013":
        return {"status": "013", "list": []}  # 데이터 없음은 정상 흐름
    if status in ("020", "021"):
        raise DartError(f"DART 사용한도 초과 (status {status}) — 잠시 뒤 다시 시도하세요.")
    if status == "901":
        raise DartError("DART 인증키가 유효하지 않습니다 (status 901).")
    raise DartError(f"DART 오류 status={status} {data.get('message', '')}")


# ─────────────────────── 회사 고유번호 ───────────────────────

def corpcode_xml() -> str:
    """전체 회사 고유번호 XML (ZIP 해제 후 캐시)."""
    fresh = (
        os.path.exists(CORPCODE_PATH)
        and time.time() - os.path.getmtime(CORPCODE_PATH) < CORPCODE_TTL
    )
    if fresh:
        return io.open(CORPCODE_PATH, encoding="utf-8").read()

    raw = _request("corpCode.xml")
    if raw[:2] != b"PK":
        # 오류는 XML/JSON 본문으로 돌아옵니다
        raise DartError(f"corpCode 응답이 ZIP 이 아닙니다: {raw[:200]!r}")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        xml = z.read(z.namelist()[0]).decode("utf-8")

    os.makedirs(CACHE_DIR, exist_ok=True)
    io.open(CORPCODE_PATH, "w", encoding="utf-8").write(xml)
    return xml


def find_corp(name: str) -> list[dict]:
    """정식 상호로 조회. DART 는 약칭이 아니라 등기 상호를 씁니다
    (메리츠화재 → '메리츠화재해상보험', KB라이프 → '케이비라이프생명보험').
    """
    root = ET.fromstring(corpcode_xml())
    hits = []
    for row in root.findall("list"):
        if (row.findtext("corp_name") or "").strip() == name.strip():
            hits.append({
                "corp_code": (row.findtext("corp_code") or "").strip(),
                "corp_name": name.strip(),
                "stock_code": (row.findtext("stock_code") or "").strip(),
                "modify_date": (row.findtext("modify_date") or "").strip(),
            })
    return hits


# ─────────────────────── 재무 ───────────────────────

def _num(text: str | None):
    """'350,685,701,000,000' → 350685701000000 · '-' → None"""
    if not text or text.strip() in ("-", ""):
        return None
    try:
        return int(text.replace(",", "").replace(" ", ""))
    except ValueError:
        return None


# fnlttSinglAcnt 의 account_nm → 우리 필드
ACCOUNTS = {
    "자산총계": "assets",
    "부채총계": "liabilities",
    "자본총계": "equity",
    "당기순이익(손실)": "net_income",
    "영업이익(손실)": "operating_income",
    "보험계약부채": "insurance_liabilities",
}


def fetch_financials(corp_code: str, year: int | str, reprt_code: str = ANNUAL) -> dict | None:
    """단일회사 주요계정. 한 번 호출하면 별도(OFS)·연결(CFS)이 함께 옵니다.

    별도 우선으로 고르고, 어느 기준인지 fs_basis 에 남깁니다.
    데이터가 없으면 None.
    """
    data = _get_json(
        "fnlttSinglAcnt.json",
        corp_code=corp_code, bsns_year=str(year), reprt_code=reprt_code,
        fs_div="OFS",  # 응답에는 두 기준이 다 들어오지만 필수 인자라 채웁니다
    )
    rows = data.get("list") or []
    if not rows:
        return None

    picked: dict[str, dict] = {"OFS": {}, "CFS": {}}
    stlm = {"OFS": "", "CFS": ""}
    corp_name = ""

    for r in rows:
        basis = r.get("fs_div")
        field = ACCOUNTS.get((r.get("account_nm") or "").strip())
        if basis not in picked or not field:
            continue
        value = _num(r.get("thstrm_amount"))
        if value is None:
            continue
        # 같은 계정이 중복으로 오면 첫 값을 유지 (당기순이익은 BS/IS 양쪽에 등장)
        picked[basis].setdefault(field, value)
        # 기준일은 재무상태표에서만 — 손익계산서는 '2025.01.01 ~ 2025.12.31' 처럼
        # 기간이라 그대로 쓰면 결산일이 1월 1일로 잘못 잡힙니다.
        if r.get("sj_div") == "BS" and not stlm[basis]:
            stlm[basis] = (r.get("thstrm_dt") or "").strip()
        corp_name = r.get("corp_name") or corp_name

    for basis in ("OFS", "CFS"):
        vals = picked[basis]
        if vals.get("assets") and vals.get("equity") is not None:
            return {
                "fs_basis": "별도" if basis == "OFS" else "연결",
                "corp_name": corp_name,
                "period": stlm[basis],
                **vals,
            }
    return None


def fetch_financials_latest(corp_code: str, years: list[int]) -> dict | None:
    """최근 연도부터 거슬러 첫 성공을 돌려줍니다 (사업보고서 제출 시점 차이 흡수)."""
    for year in years:
        try:
            got = fetch_financials(corp_code, year)
        except DartError as e:
            if "한도" in str(e) or "인증키" in str(e):
                raise
            got = None
        if got:
            got["year"] = year
            return got
    return None


# ─────────────────────── 주주 ───────────────────────

SKIP_NAMES = {"계", "합계", "소계", "-", ""}

# 같은 회사가 '삼성물산' / '삼성물산(주)' 로 다르게 적혀 옵니다. 정규화하지 않으면
# 대량보유 보고의 '특별관계자 합산 43.56%' 와 최대주주 현황의 '본인 19.34%' 가
# 나란히 떠서 같은 주주를 두 번 계상합니다.
_NAME_NOISE = re.compile(r"\(주\)|㈜|주식회사|\(유\)|유한회사|\(재\)|재단법인|\s+")


def _norm_name(name: str) -> str:
    return _NAME_NOISE.sub("", name or "").lower()


def fetch_shareholders(corp_code: str, year: int | str, limit: int = 7) -> list[dict]:
    """최대주주 및 특수관계인 (+ 상장사는 5% 이상 대량보유자).

    hyslrSttus 는 '최대주주 및 특수관계인'만 담아 국민연금 같은 기관투자자가
    빠집니다. 그래서 상장사는 majorstock(대량보유 상황보고)에서 아직 목록에
    없는 보고자만 최신 건으로 덧붙입니다.
    (majorstock 의 지분율은 특별관계자 합산이라 중복 계상을 피하려면
     이미 있는 이름은 건드리지 않아야 합니다.)
    """
    out: list[dict] = []
    seen: set[str] = set()

    data = _get_json("hyslrSttus.json", corp_code=corp_code,
                     bsns_year=str(year), reprt_code=ANNUAL)
    for r in data.get("list") or []:
        name = (r.get("nm") or "").strip()
        if name in SKIP_NAMES or _norm_name(name) in seen:
            continue
        if (r.get("stock_knd") or "").strip() == "우선주":
            continue  # 지분율은 보통주 기준으로만 표시
        stake = r.get("trmend_posesn_stock_qota_rt") or r.get("bsis_posesn_stock_qota_rt")
        try:
            pct = float(str(stake).replace(",", ""))
        except (TypeError, ValueError):
            continue
        if pct <= 0:
            continue  # 지분 0인 등기임원 등은 제외
        seen.add(_norm_name(name))
        out.append({
            "name": name,
            "stake": round(pct, 2),
            "role": (r.get("relate") or "").strip() or "최대주주 측",
            "source": "최대주주 현황",
        })

    # 5% 이상 대량보유자 (상장사만 존재) - 보고자별 최신 건
    try:
        major = _get_json("majorstock.json", corp_code=corp_code)
    except DartError:
        major = {"list": []}

    latest: dict[str, dict] = {}
    for r in major.get("list") or []:
        who = (r.get("repror") or "").strip()
        if not who or _norm_name(who) in seen:
            continue  # 최대주주 측은 '본인 지분'을 이미 넣었으므로 합산 지분을 겹쳐 쓰지 않습니다
        prev = latest.get(who)
        if prev is None or (r.get("rcept_dt") or "") >= (prev.get("rcept_dt") or ""):
            latest[who] = r

    for who, r in latest.items():
        try:
            pct = float(str(r.get("stkrt") or "").replace(",", ""))
        except ValueError:
            continue
        if pct <= 0:
            continue
        out.append({
            "name": who,
            "stake": round(pct, 2),
            "role": f"5% 이상 대량보유 ({r.get('rcept_dt', '')})",
            "source": "대량보유 상황보고",
        })

    # 두 출처를 합쳐 지분율 순으로 — 그러지 않으면 특수관계인 1%대가 국민연금 7%대를
    # 밀어내고 목록 상한에 걸립니다.
    out.sort(key=lambda x: -x["stake"])
    return out[:limit]


# ─────────────────────── 공시 원문 링크 ───────────────────────

VIEWER = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={}"

# pblntf_ty: A 정기공시 · F 외부감사관련
FILING_KINDS = (
    ("A", ("사업보고서",)),      # 재무제표 API 가 읽는 정기보고서
    ("F", ("연결감사보고서", "감사보고서")),  # 정기보고서 미제출 회사의 최선책
)


def fetch_latest_filing(corp_code: str, begin: str = "20250101") -> dict | None:
    """가장 최근 사업보고서, 없으면 감사보고서의 원문 링크.

    사업보고서를 안 내는 보험사(외국계 자회사·디지털 손보 등)가 13곳 있습니다.
    그 회사들은 재무제표 API 로 읽히지 않으므로, 최소한 감사보고서 원문으로
    바로 갈 수 있게 링크를 남겨 관리자모드에서 손으로 채울 수 있게 합니다.
    """
    end = "20991231"
    for pblntf_ty, wanted in FILING_KINDS:
        try:
            data = _get_json("list.json", corp_code=corp_code, bgn_de=begin, end_de=end,
                             pblntf_ty=pblntf_ty, page_count="20",
                             sort="date", sort_mth="desc")
        except DartError:
            continue
        for row in data.get("list") or []:
            name = (row.get("report_nm") or "").strip()
            if any(w in name for w in wanted):
                return {
                    "kind": "사업보고서" if pblntf_ty == "A" else "감사보고서",
                    "report_nm": name,
                    "rcept_dt": row.get("rcept_dt", ""),
                    "url": VIEWER.format(row.get("rcept_no", "")),
                }
    return None


# ─────────────────────── 조립 ───────────────────────

def sync_company(company: dict, years: list[int]) -> dict:
    """회사 1건의 DART 갱신 결과. 실패해도 예외를 올리지 않고 error 를 담습니다.

    재무제표를 못 읽어도 공시 원문 링크(filing)는 최대한 채워 돌려줍니다.
    """
    code = (company.get("dart_code") or "").strip()
    result = {"id": company["id"], "name": company["name"], "error": None,
              "fin": None, "shareholders": [], "filing": None}
    if not code:
        result["error"] = "dart_code 없음"
        return result

    try:
        result["filing"] = fetch_latest_filing(code)
    except DartError:
        pass  # 링크는 있으면 좋은 부가정보이지 실패 사유가 아닙니다

    try:
        fin = fetch_financials_latest(code, years)
    except DartError as e:
        result["error"] = str(e)
        return result
    if not fin:
        kind = (result["filing"] or {}).get("kind")
        result["error"] = (
            "DART 정기보고서(사업보고서) 미제출 - 감사보고서만 존재"
            if kind == "감사보고서" else
            f"재무 데이터 없음 ({'/'.join(map(str, years))})"
        )
        return result
    result["fin"] = fin

    try:
        result["shareholders"] = fetch_shareholders(code, fin["year"])
    except DartError as e:
        result["error"] = f"주주 조회 실패: {e}"  # 재무는 살리고 주주만 비웁니다
    return result


def to_eok(won: int | None) -> int | None:
    """원 → 억원 (insurers.json 단위)."""
    return None if won is None else round(won / EOK)
