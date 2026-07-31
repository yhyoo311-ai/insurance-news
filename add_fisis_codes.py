# -*- coding: utf-8 -*-
"""insurers.json 에 FISIS 회사코드(fisis_code)를 넣고, 소멸한 회사를 정리합니다. 1회성 도구.

실행:  python add_fisis_codes.py            검증만 (파일 안 바꿈)
       python add_fisis_codes.py --write    반영

자동 매칭을 쓰지 않는 이유는 DART 때와 같습니다.
이름만으로 맞추면 '하나생명보험'과 '하나손해보험'이 서로 붙고, 캐롯은 폐업 상태라
못 찾습니다. 그래서 35건을 명시 매핑하고, 저장 전에 FISIS 에서 상호를 되짚어
전건 일치를 확인한 뒤에만 씁니다.

FISIS 는 권역(partDiv)을 나눠 관리합니다 — H=생명보험, I=손해보험.
코리안리·서울보증은 우리 화면에서 '재보험·보증' 그룹이지만 FISIS 에서는 손해보험(I)입니다.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(APP_DIR, ".env"))
except ImportError:
    pass

from src import console, fisis  # noqa: E402

console.setup()

PATH = os.path.join(APP_DIR, "data", "insurers.json")

# 회사 id → (FISIS 회사코드, 권역, FISIS 등록 상호)
MAPPING = {
    # ── 생명보험 (partDiv=H) ──
    "samsung-life":        ("0010595", "H", "삼성생명보험주식회사"),
    "hanwha-life":         ("0010593", "H", "한화생명보험주식회사"),
    "kyobo-life":          ("0010597", "H", "교보생명보험주식회사"),
    "shinhan-life":        ("0010599", "H", "신한라이프생명보험주식회사"),
    "nh-life":             ("0013173", "H", "농협생명보험주식회사"),
    "miraeasset-life":     ("0010608", "H", "미래에셋생명보험주식회사"),
    "tongyang-life":       ("0010622", "H", "동양생명보험주식회사"),
    "kb-life":             ("0010616", "H", "KB라이프생명보험"),
    "heungkuk-life":       ("0010596", "H", "흥국생명보험주식회사"),
    "metlife-korea":       ("0010620", "H", "메트라이프생명보험(주)"),
    "fubon-hyundai-life":  ("0011320", "H", "푸본현대생명보험주식회사"),
    "abl-life":            ("0010594", "H", "에이비엘생명보험주식회사"),
    "kdb-life":            ("0010607", "H", "케이디비생명보험주식회사"),
    "db-life":             ("0010619", "H", "DB생명보험주식회사"),
    "ibk-pension":         ("0012455", "H", "아이비케이연금보험 주식회사"),
    "im-life":             ("0010605", "H", "아이엠라이프생명보험 주식회사"),
    "lina-life":           ("0011434", "H", "라이나생명보험주식회사"),
    "aia-korea":           ("0010615", "H", "에이아이에이생명보험 주식회사"),
    "hana-life":           ("0010618", "H", "하나생명보험주식회사"),
    "chubb-life":          ("0010625", "H", "처브라이프생명보험주식회사"),
    "kyobo-lifeplanet":    ("0013436", "H", "교보라이프플래닛생명보험주식회사"),
    # ── 손해보험 (partDiv=I) ──
    "samsung-fire":        ("0010633", "I", "삼성화재해상보험주식회사"),
    "db-insurance":        ("0010636", "I", "DB손해보험주식회사"),
    "hyundai-marine":      ("0010634", "I", "현대해상화재보험주식회사"),
    "kb-insurance":        ("0010635", "I", "주식회사KB손해보험"),
    "meritz-fire":         ("0010626", "I", "메리츠화재해상보험주식회사"),
    "hanwha-general":      ("0010627", "I", "한화손해보험주식회사"),
    "lotte-insurance":     ("0010628", "I", "롯데손해보험주식회사"),
    "nh-property":         ("0013174", "I", "농협손해보험주식회사"),
    "heungkuk-fire":       ("0010630", "I", "흥국화재해상보험주식회사"),
    "axa-korea":           ("0010653", "I", "악사손해보험주식회사"),
    "hana-insurance":      ("0011354", "I", "하나손해보험주식회사"),
    "kakaopay-insurance":  ("0019399", "I", "주식회사 카카오페이손해보험"),
    # ── 재보험·보증 (FISIS 에서는 손해보험 권역) ──
    "korean-re":           ("0010638", "I", "코리안리재보험주식회사"),
    "sgi-seoul-guarantee": ("0010637", "I", "서울보증보험주식회사"),
}

# 기준일(2025-12-31) 시점에 존재하지 않는 회사 — 목록에서 뺍니다.
# 있지도 않은 회사를 히트맵에 그리면 업계 지형을 잘못 읽게 됩니다.
REMOVED = {
    "mg-insurance": (
        "2025-09-03 금융위가 영업정지를 의결하고 보험계약 122만건을 가교보험사 "
        "예별손해보험(예금보험공사 100% 출자)으로 이전. 09-04 영업 전면 정지. "
        "FISIS 보고도 2025.06 이 마지막이고 K-ICS 는 -19.34% 까지 떨어졌습니다."
    ),
    "carrot-insurance": (
        "모회사 한화손해보험에 흡수합병. FISIS 에 [폐] 로 남아 있고 2025.09 가 "
        "마지막 보고입니다. 실적은 한화손해보험 수치에 포함됩니다."
    ),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="insurers.json 에 실제로 반영")
    args = ap.parse_args()

    try:
        fisis.api_key()
    except fisis.FisisError as e:
        print(f"[fisis] {e}")
        return 1

    print("[fisis] 회사 목록 조회 중…")
    registry = {}
    for part in (fisis.LIFE, fisis.NONLIFE):
        for row in fisis.companies(part):
            registry[(row.get("finance_cd") or "").strip()] = (
                (row.get("finance_nm") or "").strip(), part
            )
    print(f"[fisis] 생보·손보 합계 {len(registry)}개사 (폐업 포함)")

    problems = []
    for cid, (code, part, expect) in MAPPING.items():
        found = registry.get(code)
        if found is None:
            problems.append(f"  {cid}: 코드 {code} 가 FISIS 목록에 없음")
            continue
        actual, actual_part = found
        if actual != expect:
            problems.append(f"  {cid}: 코드 {code} 의 상호가 '{actual}' (기대: '{expect}')")
        elif actual_part != part:
            problems.append(f"  {cid}: 권역이 '{actual_part}' (기대: '{part}')")
        elif "[폐]" in actual:
            problems.append(f"  {cid}: '{actual}' 는 폐업 상태입니다")

    if problems:
        print("[fisis] 매핑 검증 실패  -  저장하지 않았습니다:")
        print("\n".join(problems))
        return 1
    print(f"[fisis] 매핑 {len(MAPPING)}건 상호·권역 일치 확인")

    data = json.load(io.open(PATH, encoding="utf-8"))
    companies = data["companies"]

    dropped = [c for c in companies if c["id"] in REMOVED]
    kept = [c for c in companies if c["id"] not in REMOVED]
    unmapped = [c["id"] for c in kept if c["id"] not in MAPPING]

    if dropped:
        print(f"\n[fisis] 소멸 {len(dropped)}개사 제거:")
        for c in dropped:
            print(f"  - {c['name']}: {REMOVED[c['id']]}")

    if unmapped:
        print(f"\n[fisis] 매핑 없는 회사 {len(unmapped)}건: {', '.join(unmapped)}")
        print("[fisis] 전건 매핑되어야 합니다  -  저장하지 않았습니다.")
        return 1

    for c in kept:
        code, part, name = MAPPING[c["id"]]
        c["fisis_code"], c["fisis_part"], c["fisis_name"] = code, part, name

    if not args.write:
        print(f"\n[fisis] 미리보기입니다 ({len(kept)}개사 유지). 반영하려면 --write 를 붙이세요.")
        return 0

    data["companies"] = kept
    with io.open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"\n[fisis] insurers.json 갱신  -  {len(kept)}개사에 fisis_code 부여 "
          f"(소멸 {len(dropped)}개사 제거)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
