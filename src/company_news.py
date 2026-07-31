# -*- coding: utf-8 -*-
"""회사별 최근 뉴스 조회 (네이버 검색 API).

정보사이트의 회사 패널에 띄우는 '최근 주요 뉴스 N건' 전용입니다.
매일 발송되는 다이제스트 파이프라인(src/collect.py)과는 목적이 달라
24시간 제한 없이 최근 기사에서 회사명이 실제로 언급된 것만 골라냅니다.
"""

from __future__ import annotations

import html
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from difflib import SequenceMatcher

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache")
CACHE_TTL = 30 * 60  # 30분
NAVER_URL = "https://openapi.naver.com/v1/search/news.json"

DEFAULT_COUNT = 3
FETCH_DISPLAY = 100      # 요청당 기사 수 (네이버 최대 100)
FETCH_PAGES = 2          # 쿼리당 페이지 수 — 제목에 회사명이 박힌 기사를 찾을 확률을 높입니다
TITLE_SIMILARITY = 0.60  # 같은 사건 판별 — 제목 문자열 유사도
TITLE_OVERLAP = 0.50     # 같은 사건 판별 — 핵심 토큰 겹침 계수
SHARED_TOKENS = 3        # 같은 사건 판별 — 회사명을 뺀 공유 토큰 수 (받아쓴 보도자료 대응)

# 네이버 검색 API 는 짧은 시간에 몰아치면 429/5xx 를 돌려줍니다. 스냅샷 빌드는
# 37개사 × 4요청을 병렬로 던지므로 프로세스 전체에서 간격을 지키고 재시도합니다.
MIN_INTERVAL = 0.12      # 요청 사이 최소 간격(초)
MAX_RETRY = 3
_throttle = threading.Lock()
_last_call = [0.0]

# 여러 회사를 한꺼번에 나열하는 묶음 기사. 회사명이 본문에 스쳐 나올 뿐이라
# 특정 회사의 '주요 뉴스'로는 가치가 낮아 뒤로 밀어냅니다.
ROUNDUP_MARKERS = (
    "뉴스브리핑", "브리핑", "업앤다운", "한눈에", "주요뉴스", "주요 뉴스", "이슈 종합",
    "종합]", "오늘의", "한줄뉴스", "이 아침", "조간", "석간", "굿모닝", "핫클릭",
    "머니픽", "마켓워치", "증시 요약", "시황", "미리보기", "week", "위클리",
)

# 스포츠단·문화재단 기사. 보험사 이름이 제목에 박혀 있어 그냥 두면 상위를 독식합니다
# (예: 삼성생명 여자농구단, 교보생명 교보교육재단, 흥국생명 배구단).
OFFTOPIC_MARKERS = (
    "퓨처스리그", "리그", "농구", "배구", "야구", "축구", "골프", "구단", "감독", "선수",
    "우승", "준우승", "결승", "예선", "원정", "금메달", "은메달", "메달", "수영부",
    "체육", "스포츠", "챔피언", "올림픽", "아시안게임", "국가대표", "경기력",
    "교육재단", "문화재단", "장학", "봉사", "청소년", "문화교류", "문화 교류",
    "음악회", "콘서트", "미술관", "공모전", "백일장", "마라톤", "걷기",
    "뽑는다", "채용설명회", "공채", "인턴 모집",
)

# 보험업 관련성 게이트: 회사명 말고 업(業) 이야기가 최소 하나는 있어야 합니다.
# (회사명만으로 통과시키면 스포츠단·재단 기사가 그대로 들어옵니다)
BUSINESS_TERMS = (
    "보험료", "보험금", "보험사", "보험업", "보험상품", "보험시장", "보험계약", "계약자",
    "실손", "자동차보험", "종신", "변액", "연금", "펫보험", "건강보험", "저축성", "보장성",
    "실적", "순이익", "영업이익", "적자", "흑자", "손해율", "사업비", "수입보험료", "CSM",
    "자본", "건전성", "지급여력", "K-ICS", "킥스", "IFRS17", "증자", "후순위", "신종자본",
    "인수", "매각", "M&A", "합병", "지분", "매물", "실사", "우선협상", "지배구조", "대주주",
    "금융감독원", "금감원", "금융위", "당국", "제재", "과징금", "검사", "감독규정", "보험업법",
    "소송", "분쟁", "민원", "불완전판매", "보험사기", "약관", "부지급",
    "GA", "보험대리점", "설계사", "방카슈랑스", "판매채널", "시책", "출시", "신상품",
    "배당", "밸류업", "주가", "시가총액", "실권", "공시", "등급", "신용등급",
    "해외진출", "해외법인", "현지법인", "디지털", "플랫폼", "AI", "전산", "차세대",
    "대표이사", "사장", "회장", "경영", "조직개편", "임원", "인사",
)


def _clean(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def _cache_path(key: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z가-힣_-]", "_", key)
    return os.path.join(CACHE_DIR, f"news_{safe}.json")


def _cache_get(key: str):
    try:
        path = _cache_path(key)
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


def _naver_get(url: str, headers: dict) -> list[dict] | None:
    """네이버 검색 1회 호출. 간격을 지키고, 일시적 오류는 백오프 재시도합니다.

    None 을 돌려주면 '이 요청은 포기' 라는 뜻입니다 (호출부가 다음으로 넘어감).
    """
    for attempt in range(MAX_RETRY):
        with _throttle:
            wait = MIN_INTERVAL - (time.monotonic() - _last_call[0])
            if wait > 0:
                time.sleep(wait)
            _last_call[0] = time.monotonic()

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.load(resp).get("items", [])
        except urllib.error.HTTPError as e:
            # 429(과다호출)·5xx 는 잠시 뒤 다시. 401/403(키 문제)은 재시도 무의미.
            if e.code not in (429, 500, 502, 503, 504) or attempt == MAX_RETRY - 1:
                print(f"[news] HTTP {e.code}  -  포기")
                return None
            time.sleep(0.6 * (2 ** attempt))
        except (urllib.error.URLError, OSError, ValueError) as e:
            if attempt == MAX_RETRY - 1:
                print(f"[news] {type(e).__name__}  -  포기")
                return None
            time.sleep(0.4 * (2 ** attempt))
    return None


def _domain(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc.replace("www.", "")
    except ValueError:
        return ""


def _fmt_date(pub_date: str) -> str:
    """'Mon, 27 Jul 2026 12:00:00 +0900' → '2026.07.27'."""
    months = {m: i for i, m in enumerate(
        "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}
    m = re.match(r"\w+,\s*(\d+)\s+(\w+)\s+(\d{4})", pub_date or "")
    if not m:
        return ""
    day, mon, year = m.group(1), months.get(m.group(2), 0), m.group(3)
    return f"{year}.{mon:02d}.{int(day):02d}"


def _tokens(title: str) -> set[str]:
    """제목의 의미 토큰. 기호·따옴표를 털고 1글자 토큰은 버립니다."""
    cleaned = re.sub(r"[^0-9A-Za-z가-힣]+", " ", title.lower())
    return {t for t in cleaned.split() if len(t) > 1}


def _first_token(title: str) -> str:
    """제목 맨 앞의 의미 토큰. 대괄호 머리말은 건너뜁니다."""
    stripped = re.sub(r"^\s*[\[(【][^\]\)】]*[\]\)】]\s*", "", title)
    cleaned = re.sub(r"[^0-9A-Za-z가-힣]+", " ", stripped.lower()).split()
    return cleaned[0] if cleaned else ""


def _numbers(title: str) -> set[str]:
    """구별력 있는 숫자 (3자리 이상). 같은 보도자료면 같은 수치를 씁니다."""
    return {n for n in re.findall(r"\d[\d,]*", title.replace(",", "")) if len(n) >= 3}


def _is_dup(title: str, kept: list[dict], names: list[str]) -> bool:
    """같은 사건 판별.

    같은 보도자료를 받아쓴 기사들은 제목 문자열은 꽤 다르지만 핵심 토큰을
    공유합니다("메가존클라우드-코리안리 AX 협력" 3사 버전 등). 그래서 세 신호를
    함께 봅니다 — 문자열 유사도, 겹침 계수, 회사명을 뺀 공유 토큰 수.
    """
    tk = _tokens(title)
    nums = _numbers(title)
    head = _first_token(title)
    own = set()
    for n in names:
        own |= _tokens(n)

    for k in kept:
        if SequenceMatcher(None, title, k["title"]).ratio() >= TITLE_SIMILARITY:
            return True

        other = _tokens(k["title"])
        shared = tk & other
        smaller = min(len(tk), len(other))
        if smaller >= 3 and len(shared) / smaller >= TITLE_OVERLAP:
            return True

        # 회사명은 어느 기사에나 있으니 빼고 센다 — 남은 게 3개 이상이면 같은 사건
        if len(shared - own) >= SHARED_TOKENS:
            return True

        # 같은 보도자료를 받아쓴 기사는 같은 수치를 씁니다 ("순익 182억")
        if nums & _numbers(k["title"]):
            return True

        # 제목 첫 단어가 우리 회사가 아닌 같은 주체이고(예: 협력사·인수 주체)
        # 공유 토큰이 하나라도 더 있으면 같은 사건입니다
        other_head = _first_token(k["title"])
        if head and head == other_head and head not in own and (shared - own):
            return True

    return False


# 시세를 그대로 옮긴 자동생성 기사 ("삼성생명 주가, 7월 29일 265,500원 6.84% 하락 마감").
# 패널에 이미 현재가·차트가 있으니 뉴스 자리를 차지할 이유가 없습니다.
PRICE_BOT_RE = re.compile(
    r"(주가.*(상승|하락|보합).*(마감|출발))"
    r"|(\d[\d,]*원.*(마감|출발))"
    r"|(전일 대비.*(상승|하락))"
)


def _is_roundup(title: str) -> bool:
    """묶음/브리핑 기사 판별."""
    low = title.lower()
    if any(m.lower() in low for m in ROUNDUP_MARKERS):
        return True
    # '· ' 나 ' / ' 로 여러 소식을 나열한 제목 (예: "A 펫보험 1만건 / B 지원 / C…")
    return title.count(" / ") >= 2 or title.count("·") >= 3


def _tier(title: str, desc: str, names: list[str], others: list[str]) -> int:
    """작을수록 우선. 2 이상은 버립니다.

      0  회사명이 제목에 있는 단독 기사      ← 가장 좋음
      1  회사명이 제목에 있으나 묶음/브리핑 기사
      9  버림

    본문에만 회사명이 있는 기사는 쓰지 않습니다. 실제로 돌려 보면
    '메리츠화재'가 채권자로 한 줄 언급된 홈플러스 매각 기사처럼 회사와 무관한
    기사가 올라옵니다. 3건을 억지로 채우기보다 없으면 없다고 하는 편이 낫습니다.
    """
    if not any(n in title for n in names):
        return 9

    # 제목의 주인공이 다른 보험사면 그 회사의 뉴스입니다 (우리 이름은 곁가지)
    if any(o in title for o in others) and not _is_roundup(title):
        # 두 회사가 함께 주인공인 기사(인수·제휴)는 살려야 하므로
        # 우리 이름이 더 앞에 나오는 경우만 인정합니다.
        first_own = min((title.find(n) for n in names if n in title), default=99)
        first_other = min((title.find(o) for o in others if o in title), default=99)
        if first_other < first_own:
            return 9

    # 스포츠단·문화재단은 제목에 회사명이 있어도 업 소식이 아닙니다
    if any(m in title for m in OFFTOPIC_MARKERS):
        return 9

    # 자동생성 시세 기사는 제외 (패널에 현재가·차트가 이미 있습니다)
    if PRICE_BOT_RE.search(title):
        return 9

    # 업 이야기가 전혀 없으면 회사명이 스쳐 나온 것에 불과합니다
    if not any(t in f"{title} {desc}" for t in BUSINESS_TERMS):
        return 9

    return 1 if _is_roundup(title) else 0


def fetch_company_news(
    company: dict,
    client_id: str,
    client_secret: str,
    count: int = DEFAULT_COUNT,
    exclude_keywords: list[str] | None = None,
    other_names: list[str] | None = None,
) -> list[dict]:
    """회사명이 제목·요약에 실제로 등장하는 최근 기사 count건.

    other_names 에 다른 보험사 이름들을 넘기면 '타사 뉴스에 이름만 스친 기사'를
    걸러낼 수 있어 정확도가 크게 올라갑니다.
    자격증명이 없거나 조회가 실패하면 빈 리스트를 반환합니다
    (패널은 '최근 관련 기사를 찾지 못했습니다'로 표시).
    """
    names = company.get("aliases") or [company["name"]]
    others = [n for n in (other_names or []) if n not in names]
    cache_key = f"{company['id']}_{count}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    if not client_id or not client_secret:
        return []

    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    # 회사명 단독 + 보험 문맥, 각 쿼리를 여러 페이지 받아 후보 풀을 넓힙니다.
    # 제목에 회사명이 박힌 기사만 채택하므로 풀이 넓을수록 결과가 좋아집니다.
    items: list[dict] = []
    for query in (names[0], f"{names[0]} 보험"):
        for page in range(FETCH_PAGES):
            params = urllib.parse.urlencode({
                "query": query,
                "display": FETCH_DISPLAY,
                "start": page * FETCH_DISPLAY + 1,
                "sort": "date",
            })
            got = _naver_get(f"{NAVER_URL}?{params}", headers)
            if got is None:
                print(f"[news] {company['name']} 조회 실패 ({query} p{page + 1})")
                break
            items += got
            if len(got) < FETCH_DISPLAY:
                break  # 마지막 페이지

    if not items:
        return []

    excludes = [k for k in (exclude_keywords or []) if k]

    # 등급별로 모아 둔 뒤 좋은 등급부터 채웁니다 (등급 안에서는 최신순 유지)
    buckets: dict[int, list[dict]] = {0: [], 1: []}
    seen_urls: set[str] = set()

    for item in items:
        title = _clean(item.get("title", ""))
        desc = _clean(item.get("description", ""))
        link = item.get("originallink") or item.get("link", "")

        if not title or link in seen_urls:
            continue
        if any(k in title for k in excludes):
            continue

        tier = _tier(title, desc, names, others)
        if tier > 1:
            continue

        seen_urls.add(link)
        buckets[tier].append({
            "title": title,
            "url": link,
            "summary": desc[:160],
            "date": _fmt_date(item.get("pubDate", "")),
            "source": _domain(link) or "naver",
            "_tier": tier,
        })

    picked: list[dict] = []
    for tier in (0, 1):
        for art in buckets[tier]:
            if _is_dup(art["title"], picked, names):
                continue
            picked.append({k: v for k, v in art.items() if k != "_tier"})
            if len(picked) >= count:
                _cache_put(cache_key, picked)
                return picked

    _cache_put(cache_key, picked)
    return picked
