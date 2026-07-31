# -*- coding: utf-8 -*-
"""FISIS 감독통계로 K-ICS 를 갱신하고, DART 로 못 채운 회사의 재무를 채웁니다.

실행:  python sync_fisis.py                    미리보기만 (파일 안 바꿈)
       python sync_fisis.py --write            insurers.json 에 반영
       python sync_fisis.py --write --base 202512
       python sync_fisis.py --only samsung-life,lina-life

무엇이 바뀌나
  · kics — **전 회사**. DART 에 없는 감독지표라 이 스크립트가 유일한 출처입니다.
  · 재무(자산·부채·자본·영업이익·당기순이익·보험계약부채)
    — **DART 로 검증되지 않은 회사만**. 이유는 아래.

왜 DART 검증 회사의 재무는 건드리지 않나
  두 출처의 자산총계는 원 단위까지 같지만, 부채/자본 배분이 회사에 따라 다릅니다
  (삼성생명 자본 DART 56.4조 vs FISIS 43.6조 — 감독업무보고서와 IFRS 별도재무제표의
  평가 기준 차이). 같은 화면에 두 기준을 섞으면 회사 간 비교가 깨집니다.
  그래서 **DART 가 있으면 DART 로 통일**하고, 없는 회사만 FISIS 로 채운 뒤
  fs_basis 에 출처를 남깁니다.

손익은 분기 단독값이라 4개 분기를 합산합니다 (src/fisis.py 참고).
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

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
FIN_FIELDS = ("assets", "liabilities", "equity",
              "operating_income", "net_income", "insurance_liabilities")
FISIS_BASIS = "감독업무보고서(FISIS)"


def default_base(data: dict) -> str:
    """insurers.json 의 기준일에서 조회 기준월(YYYYMM)을 만듭니다."""
    as_of = (data.get("as_of") or "").replace("-", "")
    return as_of[:6] if len(as_of) >= 6 else "202512"


def fetch(company: dict, base_mm: str) -> dict:
    out = {"id": company["id"], "name": company["name"], "snap": None, "error": ""}
    try:
        out["snap"] = fisis.snapshot(company["fisis_code"], company["fisis_part"], base_mm)
    except fisis.FisisError as e:
        out["error"] = str(e)
    except (KeyError, TypeError):
        out["error"] = "fisis_code 가 없습니다 (add_fisis_codes.py 를 먼저 실행하세요)"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="insurers.json 에 실제로 반영")
    ap.add_argument("--base", default="", help="기준월 YYYYMM (기본: as_of 에서 유도)")
    ap.add_argument("--only", default="", help="쉼표로 구분한 회사 id 만 갱신")
    args = ap.parse_args()

    try:
        fisis.api_key()
    except fisis.FisisError as e:
        print(f"[fisis] {e}")
        return 1

    data = json.load(io.open(PATH, encoding="utf-8"))
    companies = data["companies"]
    base_mm = args.base or default_base(data)

    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        targets = [c for c in companies if c["id"] in wanted]
        unknown = wanted - {c["id"] for c in targets}
        if unknown:
            print(f"[fisis] 없는 회사 id: {', '.join(sorted(unknown))}")
    else:
        targets = companies

    print(f"[fisis] {len(targets)}개사 조회 (기준월 {base_mm}, 분기 업무보고서)")

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda c: fetch(c, base_mm), targets))

    by_id = {c["id"]: c for c in companies}
    kics_rows, fin_rows, failures = [], [], []
    kics_changed = fin_changed = 0

    for res in results:
        company = by_id[res["id"]]
        if res["error"] or not res["snap"]:
            failures.append(f"  {res['name']}: {res['error'] or '데이터 없음'}")
            continue

        snap = res["snap"]

        if snap["kics"] is not None:
            before = company.get("kics")
            kics_rows.append(
                f"  {company['name']:<14} K-ICS {before!s:>7} -> {snap['kics']:>7}"
                f"   ({snap['kics_basis']})"
            )
            if args.write:
                company["kics"] = snap["kics"]
                company["kics_basis"] = snap["kics_basis"]
                company["kics_as_of"] = base_mm
                kics_changed += 1
        else:
            failures.append(f"  {res['name']}: K-ICS 값이 없습니다 (기준월 {base_mm})")

        # 재무는 DART 로 못 채운 회사만 — 기준을 섞지 않기 위해서입니다.
        # 단 이미 FISIS 로 채운 회사는 계속 FISIS 로 갱신해야 합니다.
        # (verified 만 보면 첫 실행 뒤 True 가 되어 영영 갱신되지 않습니다)
        if company.get("verified") and company.get("fs_basis") != FISIS_BASIS:
            continue

        new = {k: snap.get(k) for k in FIN_FIELDS if snap.get(k) is not None}
        if not new:
            continue

        fin_rows.append(
            f"  {company['name']:<14} "
            f"자산 {company.get('assets')!s:>9} -> {new.get('assets')!s:>9}   "
            f"자본 {company.get('equity')!s:>8} -> {new.get('equity')!s:>8}   "
            f"순익 {company.get('net_income')!s:>8} -> {new.get('net_income')!s:>8}"
        )
        if args.write:
            company.update(new)
            company["fs_basis"] = FISIS_BASIS
            company["verified"] = True
            company["fisis_as_of"] = base_mm
            fin_changed += 1

    print("\n[fisis] K-ICS")
    print("\n".join(kics_rows) if kics_rows else "  (없음)")
    print(f"\n[fisis] 재무 보강 (DART 미검증 회사만) - {len(fin_rows)}개사")
    print("\n".join(fin_rows) if fin_rows else "  (없음)")
    if failures:
        print(f"\n[fisis] 실패 {len(failures)}건:")
        print("\n".join(failures))

    if not args.write:
        print("\n[fisis] 미리보기입니다. 반영하려면 --write 를 붙여 다시 실행하세요.")
        return 0

    data["data_note"] = (
        "자산총계·부채총계·자본총계·당기순이익·영업이익·보험계약부채·주요주주는 "
        "DART 전자공시 사업보고서 값입니다(회사별 별도/연결 기준 표기). "
        "사업보고서를 내지 않는 회사는 FISIS(금융감독원 금융통계정보시스템) "
        "업무보고서 값으로 채우고 그렇게 표기합니다. "
        "K-ICS 비율은 전 회사 FISIS 업무보고서 값이며 경과조치 적용 여부를 함께 표기합니다. "
        "주가·시가총액·52주 고저는 Yahoo Finance 조회값입니다."
    )
    data["fisis_synced"] = True
    data["kics_as_of"] = base_mm

    with io.open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"\n[fisis] insurers.json 갱신 완료 - K-ICS {kics_changed}개사, 재무 {fin_changed}개사")
    if failures:
        print("[fisis] 실패한 회사는 기존 값을 유지합니다 (관리자모드에서 확인하세요).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
