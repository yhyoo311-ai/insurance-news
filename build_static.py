# -*- coding: utf-8 -*-
"""정적 스냅샷 빌드 — 어디든 업로드해 주소를 딸 수 있는 단일 HTML.

실행:  python build_static.py            → dist/index.html
       python build_static.py --open     → 만든 뒤 브라우저로 확인

무엇을 만드나
  · 히트맵 + 회사 패널이 그대로 동작하는 **파일 하나** (CSS·JS 인라인)
  · 모든 회사의 상세(주가차트·주주·재무·뉴스 3건)를 미리 구워 넣음

왜 사전 구운 JSON인가
  네이버·텔레그램 API 키를 정적 파일에 넣으면 주소를 아는 누구나 키를 볼 수 있습니다.
  그래서 빌드 시점에 로컬 키로 조회해 **결과만** 넣고, 키는 넣지 않습니다.
  주가는 빌드한 시점의 값으로 고정되므로, 최신 시세가 필요하면 다시 빌드하세요.

업로드 (아무 정적 호스팅이나 가능 — 계정만 있으면 됩니다)
  · Cloudflare Pages : dash.cloudflare.com → Workers & Pages → Create → Pages →
                       Upload assets → dist 폴더 드래그 → 주소 발급
  · Netlify Drop     : app.netlify.com/drop → dist 폴더 드래그 → 주소 발급
  · GitHub Pages     : 리포에 dist/ 를 push → Settings → Pages → 소스 지정
  · Google Drive 는 HTML을 웹페이지로 서비스하지 않으므로 위 셋 중 하나를 권장합니다.

주의: 발급된 주소는 기본적으로 누구나 열 수 있습니다. 사내 자료를 넣었다면
      호스팅의 접근 제어(Cloudflare Access, Netlify 비밀번호 보호 등)를 켜세요.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src import console  # noqa: E402

console.setup()

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(APP_DIR, "dist")
OUT_PATH = os.path.join(DIST_DIR, "index.html")
ADMIN_PATH = os.path.join(DIST_DIR, "admin", "index.html")


def read(*parts: str) -> str:
    with open(os.path.join(APP_DIR, *parts), encoding="utf-8") as f:
        return f.read()


def site_repo() -> str:
    """관리자 화면이 커밋할 대상 리포('owner/name').

    GitHub Actions 에서는 SITE_REPO 환경변수로 주고, 로컬에서는 git remote 에서 읽습니다.
    """
    env = os.environ.get("SITE_REPO", "").strip()
    if env:
        return env
    import re
    import subprocess
    try:
        out = subprocess.run(
            ["git", "remote", "get-url", "origin"], cwd=APP_DIR,
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?\s*$", out)
    return m.group(1) if m else ""


def write_admin() -> None:
    """웹 관리자 페이지 — 서버 없이 GitHub API 로 설정을 읽고 커밋합니다."""
    import webapp
    from flask import render_template

    with webapp.app.app_context():
        body = render_template("admin_static.html")

    repo = site_repo()
    if not repo:
        print("[build] 경고: 대상 리포를 알 수 없어 관리자 화면이 동작하지 않습니다 "
              "(SITE_REPO 환경변수 또는 git remote 확인).")

    html = ADMIN_PAGE
    for token, value in (
        ("/*__CSS__*/", read("static", "css", "app.css")),
        ("<!--__BODY__-->", body),
        ("/*__REPO__*/", json.dumps(repo)),
        ("/*__JS__*/", read("static", "js", "admin.js")),
    ):
        html = html.replace(token, value.replace("</script", "<\\/script"), 1)

    os.makedirs(os.path.dirname(ADMIN_PATH), exist_ok=True)
    with open(ADMIN_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[build] 관리자 -> {ADMIN_PATH}  (대상 리포 {repo or '미지정'})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--open", action="store_true", help="빌드 후 브라우저로 열기")
    args = ap.parse_args()

    # webapp 을 임포트하면 .env 로드와 데이터 조립 로직을 그대로 재사용합니다.
    import webapp
    from flask import render_template

    print("[build] 시세·재무 수집 중…")
    boot = webapp.build_overview()
    ids = [c["id"] for c in boot["companies"]]

    # 뉴스 조회는 company_news 안에서 전역 간격 제어를 받으므로 워커를 늘려도
    # 네이버 호출은 직렬화됩니다. 워커는 주로 Yahoo 조회 대기를 겹치는 용도입니다.
    print(f"[build] 회사 상세 {len(ids)}건 수집 중 (뉴스 포함)…")
    with ThreadPoolExecutor(max_workers=4) as pool:
        details = dict(zip(ids, pool.map(webapp.build_detail, ids)))
    details = {k: v for k, v in details.items() if v}

    missing_news = [d["name"] for d in details.values() if not d.get("news")]
    no_quote = [d["name"] for d in details.values() if d.get("quote_failed")]

    # 같은 Jinja 파티션을 재사용해 로컬 화면과 정적 화면이 어긋나지 않게 합니다.
    with webapp.app.app_context():
        body = render_template("_site.html", boot=boot)

    # CSS·JS 는 중괄호가 가득해 str.format 을 쓸 수 없습니다 — 토큰 치환으로 조립합니다.
    html = PAGE
    for token, value in (
        ("/*__CSS__*/", read("static", "css", "app.css")),
        ("<!--__BODY__-->", body),
        ("/*__BOOT__*/", json.dumps(boot, ensure_ascii=False)),
        ("/*__DETAILS__*/", json.dumps(details, ensure_ascii=False)),
        ("/*__JS__*/", read("static", "js", "app.js")),
    ):
        # 인라인 스크립트를 조기에 닫아버리는 문자열만 무해하게 이스케이프
        html = html.replace(token, value.replace("</script", "<\\/script"), 1)

    os.makedirs(DIST_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    write_admin()

    size_kb = os.path.getsize(OUT_PATH) / 1024
    print(f"[build] 완료 -> {OUT_PATH}  ({size_kb:,.0f} KB)")
    print(f"[build] 회사 {len(details)}개사 · 뉴스 없는 회사 {len(missing_news)}곳"
          + (f" ({', '.join(missing_news[:6])}…)" if missing_news else ""))
    if no_quote:
        print(f"[build] 시세 조회 실패: {', '.join(no_quote)}  -  티커를 확인하세요.")
    print("[build] dist/ 를 그대로 올리면 됩니다 (API 키 미포함).")

    if args.open:
        webbrowser.open("file:///" + OUT_PATH.replace("\\", "/"))
    return 0


PAGE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>한국 보험사 정보 시스템</title>
<style>
/*__CSS__*/
</style>
</head>
<body>
<header class="topbar">
  <div class="brand">한국 보험사 정보 시스템
    <span class="sub">Korea Insurance Information System · 스냅샷</span></div>
  <nav class="topnav">
    <a href="admin/">⚙ 관리자</a>
    <button type="button" id="theme" title="라이트/다크 전환">◐</button>
  </nav>
</header>

<!--__BODY__-->

<script>
(function () {
  var btn = document.getElementById('theme');
  var saved = localStorage.getItem('theme');
  if (saved) document.documentElement.dataset.theme = saved;
  btn.addEventListener('click', function () {
    var cur = document.documentElement.dataset.theme;
    if (!cur) cur = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    var next = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    localStorage.setItem('theme', next);
  });
})();
</script>
<script>window.__BOOT__ = /*__BOOT__*/;</script>
<script>window.__DETAILS__ = /*__DETAILS__*/;</script>
<script>
/*__JS__*/
</script>
</body>
</html>
"""


ADMIN_PAGE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>관리자 · 한국 보험사 정보 시스템</title>
<style>
/*__CSS__*/
</style>
</head>
<body>
<!--__BODY__-->

<script>
(function () {
  var btn = document.getElementById('theme');
  var saved = localStorage.getItem('theme');
  if (saved) document.documentElement.dataset.theme = saved;
  btn.addEventListener('click', function () {
    var cur = document.documentElement.dataset.theme;
    if (!cur) cur = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    var next = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    localStorage.setItem('theme', next);
  });
})();
</script>
<script>
window.__REPO__ = /*__REPO__*/;
window.__BRANCH__ = 'main';
</script>
<script>
/*__JS__*/
</script>
</body>
</html>
"""


if __name__ == "__main__":
    sys.exit(main())
