# -*- coding: utf-8 -*-
"""Genie's Insurance Note — 한국 보험사 정보 노트 (로컬 실행용).

실행:  python webapp.py   → 브라우저에서 http://127.0.0.1:5000

화면
  /                  히트맵 — 생명·손해·재보험 보험사를 시가총액/총자산 크기로 표시
                     타일 클릭 → 주가차트·주주·재무분석·최근 뉴스 패널
  /admin/news        관리자모드 · 뉴스·텔레그램 설정 (기존 dashboard.py 기능)
  /admin/companies   관리자모드 · 보험사 데이터 (총자산·자본·순이익·K-ICS·주주 수정)
"""

from __future__ import annotations

import os
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from threading import Timer

from flask import (Flask, jsonify, redirect, render_template, request,
                   send_from_directory, url_for)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src import console, dart, market, settings_store as store
from src.company_news import fetch_company_news

console.setup()

APP_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)

NAVER_ID = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")


# ─────────────────────── 데이터 조립 ───────────────────────

def build_overview() -> dict:
    """히트맵에 필요한 만큼만 담은 전체 회사 목록."""
    data = store.load_insurers()
    companies = data["companies"]

    # 상장사 시세는 네트워크 대기가 대부분이라 병렬로 받습니다.
    listed = [c for c in companies if c.get("ticker")]
    with ThreadPoolExecutor(max_workers=8) as pool:
        quotes = dict(zip(
            (c["id"] for c in listed),
            pool.map(lambda c: market.fetch_chart(c["ticker"]), listed),
        ))
        caps = dict(zip(
            (c["id"] for c in listed),
            pool.map(lambda c: market.fetch_market_cap(c["ticker"]), listed),
        ))

    tiles = []
    for c in companies:
        quote = quotes.get(c["id"])
        cap = caps.get(c["id"])
        tiles.append({
            "id": c["id"],
            "name": c["name"],
            "name_en": c.get("name_en", ""),
            "group": c["group"],
            "listed": bool(c.get("ticker")),
            "ticker": c.get("ticker"),
            "change_pct": quote["change_pct"] if quote else None,
            "price": quote["price"] if quote else None,
            "market_cap": cap,
            "assets": c.get("assets"),
            "kics": c.get("kics"),
            "quote_failed": bool(c.get("ticker")) and quote is None,
            "note": c.get("note", ""),
        })

    verified = sum(1 for c in companies if c.get("verified"))
    return {
        "groups": data["groups"],
        "as_of": data.get("as_of", ""),
        "data_note": data.get("data_note", ""),
        "verified_count": verified,
        "unverified_count": len(companies) - verified,
        "usdkrw": market.fetch_usdkrw(),
        "summary": summarize(tiles, data),
        "companies": tiles,
    }


def summarize(tiles: list[dict], data: dict) -> dict:
    """상단 요약 지표 — 화면을 열자마자 업계 상태가 보이도록.

    K-ICS 는 평균이 아니라 **중앙값**을 씁니다. 회사 규모 차이가 커서 단순평균은
    소형사 한 곳(예: 400%대)에 크게 끌려가고, 가중평균은 '가중 기준'을 또 설명해야 합니다.
    중앙값은 '가운데 회사가 어디쯤인지'를 왜곡 없이 보여줍니다.
    """
    changes = [t["change_pct"] for t in tiles if t["change_pct"] is not None]
    kics = sorted(t["kics"] for t in tiles if t.get("kics") is not None)
    mid = (
        None if not kics
        else kics[len(kics) // 2] if len(kics) % 2
        else round((kics[len(kics) // 2 - 1] + kics[len(kics) // 2]) / 2, 2)
    )
    return {
        "total_assets": sum(t["assets"] or 0 for t in tiles),
        "company_count": len(tiles),
        "listed_count": sum(1 for t in tiles if t["listed"]),
        "up": sum(1 for c in changes if c > 0),
        "down": sum(1 for c in changes if c < 0),
        "flat": sum(1 for c in changes if c == 0),
        "kics_median": mid,
        "kics_as_of": data.get("kics_as_of", ""),
        "as_of": data.get("as_of", ""),
    }


def build_detail(company_id: str) -> dict | None:
    data = store.load_insurers()
    company = next((c for c in data["companies"] if c["id"] == company_id), None)
    if company is None:
        return None

    # 다른 보험사 이름들을 함께 넘겨 '타사 뉴스에 이름만 스친 기사'를 걸러냅니다
    other_names = [
        alias
        for other in data["companies"] if other["id"] != company_id
        for alias in (other.get("aliases") or [other["name"]])
    ]

    detail = market.enrich(company)
    detail["news"] = fetch_company_news(
        company, NAVER_ID, NAVER_SECRET,
        count=3,
        exclude_keywords=store.load_settings().get("exclude_keywords", []),
        other_names=other_names,
    )
    detail["news_available"] = bool(NAVER_ID and NAVER_SECRET)
    detail["as_of"] = data.get("as_of", "")
    detail["usdkrw"] = market.fetch_usdkrw()
    detail["group_name"] = next(
        (g["name"] for g in data["groups"] if g["id"] == company["group"]), company["group"]
    )
    detail["group_no"] = next(
        (g["no"] for g in data["groups"] if g["id"] == company["group"]), ""
    )
    return detail


# ─────────────────────── 메인 사이트 ───────────────────────

@app.route("/fonts/<path:filename>")
def fonts(filename: str):
    """폰트를 /fonts/ 로 서비스합니다.

    정적 스냅샷은 CSS 가 HTML 안에 인라인되어 상대경로가 루트 기준이 됩니다.
    로컬 Flask 는 CSS 가 /static/css/ 에 있어 상대경로가 어긋납니다.
    둘 다 `/fonts/...` 하나로 맞추려고 이 라우트를 둡니다.
    """
    return send_from_directory(os.path.join(APP_DIR, "static", "fonts"), filename,
                               max_age=60 * 60 * 24 * 365)


@app.route("/")
def index():
    return render_template("index.html", boot=build_overview())


@app.route("/api/overview")
def api_overview():
    return jsonify(build_overview())


@app.route("/api/company/<company_id>")
def api_company(company_id: str):
    detail = build_detail(company_id)
    if detail is None:
        return jsonify({"error": "not_found"}), 404
    return jsonify(detail)


# ─────────────────────── 관리자모드 ───────────────────────

@app.route("/admin")
def admin_home():
    return redirect(url_for("admin_news"))


@app.route("/admin/news")
def admin_news():
    return render_template(
        "admin_news.html",
        s=store.load_settings(),
        msg=request.args.get("msg", ""),
        ok=request.args.get("ok", "1") == "1",
    )


@app.route("/admin/news/apply", methods=["POST"])
def admin_news_apply():
    store.save_settings(store.parse_news_form(request.form))
    ok, msg = store.git_commit_push("settings.json", message="Update news settings via admin")
    return redirect(url_for("admin_news", msg=msg, ok="1" if ok else "0"))


@app.route("/admin/news/preview", methods=["POST"])
def admin_news_preview():
    # 미리보기에 반영되도록 먼저 저장·배포한 뒤 워크플로우를 실행합니다.
    store.save_settings(store.parse_news_form(request.form))
    ok, msg = store.git_commit_push("settings.json", message="Update news settings via admin")
    if ok:
        ok, msg2 = store.trigger_workflow()
        msg = f"{msg} / {msg2}"
    return redirect(url_for("admin_news", msg=msg, ok="1" if ok else "0"))


@app.route("/admin/companies")
def admin_companies():
    data = store.load_insurers()
    return render_template(
        "admin_companies.html",
        data=data,
        group_names={g["id"]: g["name"] for g in data["groups"]},
        msg=request.args.get("msg", ""),
        ok=request.args.get("ok", "1") == "1",
    )


@app.route("/admin/companies/apply", methods=["POST"])
def admin_companies_apply():
    data = store.load_insurers()
    data["as_of"] = (request.form.get("as_of") or data.get("as_of", "")).strip()

    for c in data["companies"]:
        cid = c["id"]
        c["assets"] = store.as_int(request.form.get(f"assets_{cid}"), c.get("assets") or 0)
        c["equity"] = store.as_int(request.form.get(f"equity_{cid}"), c.get("equity") or 0)
        c["net_income"] = store.as_int(request.form.get(f"ni_{cid}"), c.get("net_income") or 0)
        # 비워두면 그 항목은 표시하지 않습니다 (0 으로 채우면 '부채 0원'이 됩니다)
        for field, key in (("liab", "liabilities"), ("insliab", "insurance_liabilities"),
                           ("oi", "operating_income")):
            raw = (request.form.get(f"{field}_{cid}") or "").strip()
            if raw == "":
                c.pop(key, None)
            else:
                c[key] = store.as_int(raw, c.get(key) or 0)
        c["kics"] = store.as_float(request.form.get(f"kics_{cid}"), c.get("kics"))
        c["ticker"] = (request.form.get(f"ticker_{cid}") or "").strip() or None
        c["listed"] = bool(c["ticker"])
        c["verified"] = request.form.get(f"verified_{cid}") == "on"
        c["shareholders"] = _parse_shareholders(
            request.form.get(f"sh_{cid}"), c.get("shareholders", [])
        )

    store.save_insurers(data)
    ok, msg = store.git_commit_push(
        os.path.join("data", "insurers.json"), message="Update insurer data via admin"
    )
    return redirect(url_for("admin_companies", msg=msg, ok="1" if ok else "0"))


@app.route("/admin/companies/sync-dart", methods=["POST"])
def admin_companies_sync():
    """DART 사업보고서 값으로 재무·주주를 갱신합니다 (37개사, 1~2분).

    K-ICS 는 DART 에 없는 감독지표라 건드리지 않습니다.
    티커도 Yahoo 로 검증한 값이라 DART 의 오래된 stock_code 로 덮지 않습니다.
    """
    try:
        dart.api_key()
    except dart.DartError as e:
        return redirect(url_for("admin_companies", msg=str(e), ok="0"))

    data = store.load_insurers()
    companies = data["companies"]
    years = [2025, 2024]

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda c: dart.sync_company(c, years), companies))

    by_id = {c["id"]: c for c in companies}
    updated, failed = 0, []

    for res in results:
        company = by_id[res["id"]]
        if res.get("filing"):
            company["dart_filing"] = res["filing"]
        if not res["fin"]:
            failed.append(company["name"])
            continue

        fin = res["fin"]
        for key, won in (
            ("assets", fin.get("assets")),
            ("liabilities", fin.get("liabilities")),
            ("equity", fin.get("equity")),
            ("net_income", fin.get("net_income")),
            ("operating_income", fin.get("operating_income")),
            ("insurance_liabilities", fin.get("insurance_liabilities")),
        ):
            value = dart.to_eok(won)
            if value is not None:
                company[key] = value
        company["fs_basis"] = fin["fs_basis"]
        company["dart_year"] = fin["year"]
        company["dart_period"] = fin.get("period", "")
        company["verified"] = True
        if res["shareholders"]:
            company["shareholders"] = res["shareholders"]
        updated += 1

    periods = [c.get("dart_period", "") for c in companies if c.get("dart_period")]
    if periods:
        common = max(set(periods), key=periods.count)
        date = common.split(" ")[0].replace(".", "-")
        if len(date) == 10:
            data["as_of"] = date

    store.save_insurers(data)
    ok, git_msg = store.git_commit_push(
        os.path.join("data", "insurers.json"), message="Sync insurer financials from DART"
    )
    msg = f"DART 갱신 완료 — {updated}개사 반영, 기준일 {data.get('as_of', '?')}."
    if failed:
        msg += f" 정기보고서 미제출 {len(failed)}개사는 기존 값 유지: {', '.join(failed)}."
    return redirect(url_for("admin_companies", msg=f"{msg} / {git_msg}", ok="1" if ok else "0"))


def _parse_shareholders(text: str, fallback: list[dict]) -> list[dict]:
    """'이름 | 지분% | 구분' 한 줄씩. 비우면 기존 값을 유지합니다."""
    if text is None:
        return fallback
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        name = parts[0]
        if not name:
            continue
        out.append({
            "name": name,
            "stake": store.as_float(parts[1] if len(parts) > 1 else "", None),
            "role": parts[2] if len(parts) > 2 else "",
        })
    return out or fallback


# ─────────────────────── 실행 ───────────────────────

@app.template_filter("sh_text")
def sh_text(shareholders: list[dict]) -> str:
    """주주 리스트를 편집용 텍스트로."""
    rows = []
    for s in shareholders or []:
        stake = "" if s.get("stake") is None else f"{s['stake']:g}"
        rows.append(f"{s.get('name','')} | {stake} | {s.get('role','')}")
    return "\n".join(rows)


def _open_browser():
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    Timer(1.0, _open_browser).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
