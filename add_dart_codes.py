# -*- coding: utf-8 -*-
"""insurers.json 에 DART 고유번호(dart_code)를 넣습니다. 1회성 도구.

DART 는 약칭이 아니라 등기 상호를 쓰므로 아래 매핑은 corpCode.xml 에서
**정식 상호로 정확히 조회해** 확인한 값입니다. 자동 유사도 매칭은 쓰지 않습니다
('삼성생명'이 지주회사 '삼성'과 100% 매칭되는 사고가 납니다).

실행:  python add_dart_codes.py
검증:  각 코드의 등기 상호를 corpCode.xml 로 되짚어 확인한 뒤 저장합니다.
"""

from __future__ import annotations

import io
import json
import os
import sys
import xml.etree.ElementTree as ET

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(APP_DIR, ".env"))
except ImportError:
    pass

from src import console, dart  # noqa: E402

console.setup()

PATH = os.path.join(APP_DIR, "data", "insurers.json")

# 회사 id → (DART 고유번호, 등기 상호)
MAPPING = {
    # 생명보험
    "samsung-life":        ("00126256", "삼성생명"),
    "hanwha-life":         ("00113058", "한화생명"),
    "kyobo-life":          ("00112882", "교보생명보험"),
    "shinhan-life":        ("00137517", "신한라이프생명보험"),
    "nh-life":             ("00909349", "농협생명보험"),
    "miraeasset-life":     ("00112332", "미래에셋생명"),
    "tongyang-life":       ("00117267", "동양생명"),
    "kb-life":             ("00160393", "케이비라이프생명보험"),
    "heungkuk-life":       ("00167068", "흥국생명보험"),
    "metlife-korea":       ("00171104", "메트라이프생명보험"),
    "fubon-hyundai-life":  ("00459844", "푸본현대생명보험"),
    "abl-life":            ("00148391", "에이비엘생명보험"),
    "kdb-life":            ("00104069", "케이디비생명보험"),
    "db-life":             ("00168933", "DB생명보험"),
    "ibk-pension":         ("00844635", "아이비케이연금보험"),
    "im-life":             ("00124063", "아이엠라이프생명보험"),
    "lina-life":           ("00504232", "라이나생명보험"),
    "aia-korea":           ("01295517", "에이아이에이생명보험"),
    "hana-life":           ("00187123", "하나생명보험"),
    "chubb-life":          ("00203102", "처브라이프생명보험"),
    "kyobo-lifeplanet":    ("00992622", "교보라이프플래닛생명보험"),
    # 손해보험
    "samsung-fire":        ("00139214", "삼성화재해상보험"),
    "db-insurance":        ("00159102", "DB손해보험"),
    "hyundai-marine":      ("00164973", "현대해상"),
    "kb-insurance":        ("00120216", "KB손해보험"),
    "meritz-fire":         ("00117744", "메리츠화재해상보험"),
    "hanwha-general":      ("00135917", "한화손해보험"),
    "lotte-insurance":     ("00113562", "롯데손해보험"),
    "nh-property":         ("00908155", "NH농협손해보험"),
    "heungkuk-fire":       ("00103176", "흥국화재"),
    "axa-korea":           ("00383198", "악사손해보험"),
    "mg-insurance":        ("00962861", "엠지손해보험"),
    "hana-insurance":      ("00471891", "하나손해보험"),
    "carrot-insurance":    ("01393934", "캐롯손해보험"),
    "kakaopay-insurance":  ("01603877", "카카오페이손해보험"),
    # 재보험·보증
    "korean-re":           ("00113191", "코리안리"),
    "sgi-seoul-guarantee": ("00112998", "서울보증보험"),
}


def main() -> int:
    print("[dart] 회사 고유번호 목록 확인 중…")
    root = ET.fromstring(dart.corpcode_xml())
    by_code = {}
    for row in root.findall("list"):
        by_code[(row.findtext("corp_code") or "").strip()] = (row.findtext("corp_name") or "").strip()

    problems = []
    for cid, (code, expect) in MAPPING.items():
        actual = by_code.get(code)
        if actual is None:
            problems.append(f"  {cid}: 코드 {code} 가 DART 목록에 없음")
        elif actual != expect:
            problems.append(f"  {cid}: 코드 {code} 의 상호가 '{actual}' (기대: '{expect}')")

    if problems:
        print("[dart] 매핑 검증 실패  -  저장하지 않았습니다:")
        print("\n".join(problems))
        return 1
    print(f"[dart] 매핑 {len(MAPPING)}건 상호 일치 확인")

    data = json.load(io.open(PATH, encoding="utf-8"))
    missing = []
    for c in data["companies"]:
        entry = MAPPING.get(c["id"])
        if not entry:
            missing.append(c["id"])
            continue
        c["dart_code"], c["dart_name"] = entry

    with io.open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"[dart] insurers.json 갱신  -  {len(data['companies']) - len(missing)}개사에 dart_code 부여")
    if missing:
        print(f"[dart] 매핑 없는 회사: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
