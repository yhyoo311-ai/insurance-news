# -*- coding: utf-8 -*-
"""DART 공시값으로 보험사 재무·주주를 갱신합니다.

실행:  python sync_dart.py                 미리보기만 (파일 안 바꿈)
       python sync_dart.py --write         insurers.json 에 반영
       python sync_dart.py --write --year 2025
       python sync_dart.py --only samsung-life,kyobo-life

무엇이 바뀌나
  · assets(자산총계) · liabilities(부채총계) · equity(자본총계)
  · net_income(당기순이익) · operating_income(영업이익) · insurance_liabilities(보험계약부채)
  · shareholders(최대주주 및 특수관계인 + 상장사는 5% 이상 대량보유자)
  · verified=true, fs_basis(별도/연결), dart_period, dart_year

무엇이 안 바뀌나
  · K-ICS 비율 — DART 재무제표에 없는 감독지표입니다. 손으로 관리하세요.
  · ticker — Yahoo Finance 로 검증한 값이라 DART 의 (오래된) stock_code 를 믿지 않습니다.
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

from src import console, dart, settings_store  # noqa: E402

console.setup()

PATH = os.path.join(APP_DIR, "data", "insurers.json")


def fmt_eok(v) -> str:
    """억원 값을 조/억 단위로."""
    if v is None:
        return "-"
    if abs(v) >= 10000:
        return f"{v / 10000:,.1f}조"
    return f"{v:,}억"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="insurers.json 에 실제로 반영")
    ap.add_argument("--year", type=int, default=None, help="기준 사업연도 (기본: 최근 2개 연도 시도)")
    ap.add_argument("--only", default="", help="쉼표로 구분한 회사 id 만 갱신")
    args = ap.parse_args()

    try:
        dart.api_key()
    except dart.DartError as e:
        print(f"[dart] {e}")
        return 1

    data = json.load(io.open(PATH, encoding="utf-8"))
    companies = data["companies"]

    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        targets = [c for c in companies if c["id"] in wanted]
        unknown = wanted - {c["id"] for c in targets}
        if unknown:
            print(f"[dart] 없는 회사 id: {', '.join(sorted(unknown))}")
    else:
        targets = companies

    years = [args.year] if args.year else [2025, 2024]
    print(f"[dart] {len(targets)}개사 조회 (사업연도 {'/'.join(map(str, years))}, 사업보고서 기준)")

    # DART 호출은 dart.py 안에서 전역 간격 제어를 받으므로 워커를 늘려도 안전합니다.
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda c: dart.sync_company(c, years), targets))

    by_id = {c["id"]: c for c in companies}
    rows, failures, changed = [], [], 0

    for res in results:
        company = by_id[res["id"]]

        # 공시 원문 링크는 재무를 못 읽어도 남깁니다 (관리자가 직접 확인·입력할 수 있게)
        if args.write and res["filing"]:
            company["dart_filing"] = res["filing"]

        if res["error"] and not res["fin"]:
            link = (res["filing"] or {}).get("report_nm", "")
            failures.append(f"  {res['name']}: {res['error']}"
                            + (f" [{link}]" if link else ""))
            continue

        fin = res["fin"]
        new = {
            "assets": dart.to_eok(fin.get("assets")),
            "liabilities": dart.to_eok(fin.get("liabilities")),
            "equity": dart.to_eok(fin.get("equity")),
            "net_income": dart.to_eok(fin.get("net_income")),
            "operating_income": dart.to_eok(fin.get("operating_income")),
            "insurance_liabilities": dart.to_eok(fin.get("insurance_liabilities")),
        }

        rows.append(
            f"  {company['name']:<12} {fin['fs_basis']} {fin['year']}  "
            f"자산 {fmt_eok(company.get('assets')):>10} -> {fmt_eok(new['assets']):>10}   "
            f"자본 {fmt_eok(company.get('equity')):>9} -> {fmt_eok(new['equity']):>9}   "
            f"순익 {fmt_eok(company.get('net_income')):>8} -> {fmt_eok(new['net_income']):>8}   "
            f"주주 {len(res['shareholders'])}건"
            + (f"   [주주오류] {res['error']}" if res["error"] else "")
        )

        if args.write:
            company.update({k: v for k, v in new.items() if v is not None})
            company["fs_basis"] = fin["fs_basis"]
            company["dart_year"] = fin["year"]
            company["dart_period"] = fin.get("period", "")
            company["verified"] = True
            if res["shareholders"]:
                company["shareholders"] = res["shareholders"]
            changed += 1

    print("\n".join(rows) if rows else "  (성공한 회사 없음)")
    if failures:
        print(f"\n[dart] 실패 {len(failures)}건:")
        print("\n".join(failures))

    if not args.write:
        print("\n[dart] 미리보기입니다. 반영하려면 --write 를 붙여 다시 실행하세요.")
        return 0

    # 기준일은 가장 흔한 결산일로 맞춥니다
    periods = [c.get("dart_period", "") for c in companies if c.get("dart_period")]
    if periods:
        common = max(set(periods), key=periods.count)
        date = common.split(" ")[0].replace(".", "-")
        if len(date) == 10:
            data["as_of"] = date

    # 문구는 settings_store 한 곳에만 둡니다 — 두 sync 가 각자 쓰면 서로 지웁니다.
    data["data_note"] = settings_store.DATA_NOTE
    data["dart_synced"] = True

    with io.open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"\n[dart] insurers.json 갱신 완료 - {changed}개사, 기준일 {data.get('as_of', '?')}")
    if failures:
        print("[dart] 실패한 회사는 기존 값을 유지합니다 (관리자모드에서 확인하세요).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
