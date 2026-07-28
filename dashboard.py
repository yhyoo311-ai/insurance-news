# -*- coding: utf-8 -*-
"""보험 뉴스 다이제스트 설정 대시보드 (로컬 실행용).

실행:  python dashboard.py   → 브라우저에서 http://127.0.0.1:5000
동작:  키워드·주제 비중을 편집하고 [반영] 을 누르면
       settings.json 저장 → git 커밋·푸시 → 익일 오전 7시 뉴스부터 적용.
       [지금 미리보기 발송] 은 클라우드 워크플로우를 즉시 실행해 채널로 보냄.
"""

import json
import os
import re
import subprocess
import webbrowser
from threading import Timer

import requests
from flask import Flask, redirect, request, url_for

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(APP_DIR, "settings.json")

app = Flask(__name__)


# ─────────────────────── 설정 로드/저장 ───────────────────────

def load_settings() -> dict:
    """settings.json 이 있으면 그 값을, 없으면 config.py 기본값을 반환."""
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            return json.load(f)
    import config
    return {
        "naver_search_queries": config.NAVER_SEARCH_QUERIES,
        "exclude_keywords": config.EXCLUDE_KEYWORDS,
        "importance_keywords": config.IMPORTANCE_KEYWORDS,
        "pinned_companies": config.PINNED_COMPANIES,
        "pinned_max": config.PINNED_MAX,
        "sections": config.SECTIONS,
    }


def save_settings(data: dict) -> None:
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─────────────────────── 폼 파싱 유틸 ───────────────────────

def _lines(text: str) -> list[str]:
    return [x.strip() for x in (text or "").splitlines() if x.strip()]


def _terms(text: str) -> list[str]:
    """줄바꿈/콤마 모두 구분자로 인정."""
    raw = re.split(r"[\n,]", text or "")
    return [x.strip() for x in raw if x.strip()]


def _parse_importance(text: str) -> dict:
    d = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        k, v = line.rsplit(":", 1)
        k = k.strip()
        try:
            d[k] = int(v.strip())
        except ValueError:
            continue
    return d


def _int(val, default: int) -> int:
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return default


# ─────────────────────── git / 워크플로우 ───────────────────────

def _git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=APP_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


def git_commit_push() -> tuple[bool, str]:
    _git("add", "settings.json")
    diff = _git("diff", "--cached", "--quiet")
    if diff.returncode == 0:
        return True, "변경 사항이 없어 커밋을 건너뛰었습니다 (이미 최신)."
    c = _git("commit", "-m", "Update settings via dashboard")
    if c.returncode != 0:
        return False, f"커밋 실패: {c.stderr or c.stdout}"
    p = _git("push", "origin", "main")
    if p.returncode != 0:
        return False, f"푸시 실패: {p.stderr or p.stdout}"
    return True, "GitHub에 배포 완료 — 익일 오전 7시 뉴스부터 반영됩니다."


def _repo_slug() -> str:
    r = _git("remote", "get-url", "origin")
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?\s*$", r.stdout.strip())
    return m.group(1) if m else ""


def _github_token() -> str:
    p = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        cwd=APP_DIR, capture_output=True, text=True,
    )
    for line in p.stdout.splitlines():
        if line.startswith("password="):
            return line[len("password="):]
    return ""


def trigger_workflow() -> tuple[bool, str]:
    slug = _repo_slug()
    token = _github_token()
    if not slug or not token:
        return False, "GitHub 정보를 찾지 못했습니다 (remote/자격증명 확인)."
    resp = requests.post(
        f"https://api.github.com/repos/{slug}/actions/workflows/daily.yml/dispatches",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        json={"ref": "main"},
        timeout=20,
    )
    if resp.status_code == 204:
        return True, "미리보기 발송 요청됨 — 1~2분 뒤 텔레그램 채널을 확인하세요."
    return False, f"실행 실패: HTTP {resp.status_code} {resp.text[:200]}"


# ─────────────────────── 라우트 ───────────────────────

@app.route("/")
def index():
    return render(load_settings(), request.args.get("msg", ""), request.args.get("ok", "1") == "1")


@app.route("/apply", methods=["POST"])
def apply():
    data = parse_form(request.form)
    save_settings(data)
    ok, msg = git_commit_push()
    return redirect(url_for("index", msg=msg, ok="1" if ok else "0"))


@app.route("/preview", methods=["POST"])
def preview():
    # 먼저 현재 폼 내용을 저장·배포한 뒤 실행해야 미리보기에 반영됨
    data = parse_form(request.form)
    save_settings(data)
    ok, msg = git_commit_push()
    if ok:
        ok2, msg2 = trigger_workflow()
        msg = f"{msg} / {msg2}"
        ok = ok2
    return redirect(url_for("index", msg=msg, ok="1" if ok else "0"))


def parse_form(form) -> dict:
    sections = []
    count = _int(form.get("section_count"), 0)
    for i in range(count):
        name = (form.get(f"sec_name_{i}") or "").strip()
        if not name:
            continue
        sections.append({
            "name": name,
            "min": max(0, _int(form.get(f"sec_min_{i}"), 3)),
            "max": max(1, _int(form.get(f"sec_max_{i}"), 5)),
            "terms": _terms(form.get(f"sec_terms_{i}")),
        })
    return {
        "naver_search_queries": _lines(form.get("naver_search_queries")),
        "exclude_keywords": _lines(form.get("exclude_keywords")),
        "importance_keywords": _parse_importance(form.get("importance_keywords")),
        "pinned_companies": _lines(form.get("pinned_companies")),
        "pinned_max": max(0, _int(form.get("pinned_max"), 2)),
        "sections": sections,
    }


# ─────────────────────── 렌더링 ───────────────────────

def esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render(s: dict, msg: str, ok: bool) -> str:
    sections = s.get("sections", [])
    blanks = 2  # 새 섹션 추가용 빈 슬롯
    total = len(sections) + blanks

    sec_html = ""
    for i in range(total):
        q = sections[i] if i < len(sections) else {"name": "", "min": 3, "max": 5, "terms": []}
        terms = "\n".join(q.get("terms", []))
        order = f'<span class="ord">{i+1}</span>' if i < len(sections) else '<span class="ord new">+</span>'
        catchall = " (키워드 비우면 = 기타: 나머지 전부 수용)" if not q.get("terms") and q.get("name") else ""
        sec_html += f"""
        <div class="quota">
          <div class="qrow">
            <label>{order} 섹션 이름<input name="sec_name_{i}" value="{esc(q.get('name',''))}" placeholder="(비우면 삭제)"></label>
            <label class="minbox">최소<input type="number" min="0" name="sec_min_{i}" value="{esc(q.get('min',3))}"></label>
            <label class="minbox">최대<input type="number" min="1" name="sec_max_{i}" value="{esc(q.get('max',5))}"></label>
          </div>
          <label>포함 키워드 (제목 우선 · 줄바꿈/콤마 구분){catchall}
            <textarea name="sec_terms_{i}" rows="2">{esc(terms)}</textarea>
          </label>
        </div>"""

    imp = "\n".join(f"{k}: {v}" for k, v in s.get("importance_keywords", {}).items())
    banner = ""
    if msg:
        color = "#0a7d33" if ok else "#c0341d"
        bg = "#e8f7ee" if ok else "#fdecea"
        banner = f'<div class="banner" style="color:{color};background:{bg}">{esc(msg)}</div>'

    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>보험 뉴스 다이제스트 설정</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: -apple-system, "Segoe UI", "Malgun Gothic", sans-serif; max-width: 860px;
          margin: 0 auto; padding: 24px 18px 80px; background:#fafafa; color:#1a1a1a; }}
  h1 {{ font-size: 22px; margin-bottom: 4px; }}
  .sub {{ color:#666; font-size:13px; margin-bottom:18px; }}
  fieldset {{ border:1px solid #ddd; border-radius:10px; padding:16px; margin:16px 0; background:#fff; }}
  legend {{ font-weight:700; padding:0 8px; }}
  label {{ display:block; font-size:13px; color:#444; margin:8px 0; }}
  textarea, input {{ width:100%; box-sizing:border-box; padding:8px; border:1px solid #ccc;
                     border-radius:8px; font-size:14px; margin-top:4px; font-family:inherit; }}
  textarea {{ resize:vertical; }}
  .quota {{ border:1px dashed #ccc; border-radius:8px; padding:10px; margin:10px 0; background:#fcfcfc; }}
  .qrow {{ display:flex; gap:12px; }}
  .qrow > label {{ flex:1; }}
  .minbox {{ max-width:160px; }}
  .hint {{ color:#888; font-size:12px; margin-top:2px; }}
  .bar {{ position:fixed; left:0; right:0; bottom:0; background:#fff; border-top:1px solid #ddd;
          padding:12px 18px; display:flex; gap:12px; justify-content:center; }}
  button {{ font-size:15px; font-weight:600; padding:11px 20px; border-radius:9px; border:0; cursor:pointer; }}
  .apply {{ background:#1f6feb; color:#fff; }}
  .preview {{ background:#eee; color:#222; }}
  .banner {{ padding:12px 14px; border-radius:9px; font-size:14px; margin-bottom:14px; }}
  .cols {{ display:flex; gap:14px; }} .cols > label {{ flex:1; }}
  .ord {{ display:inline-block; min-width:20px; height:20px; line-height:20px; text-align:center;
          background:#1f6feb; color:#fff; border-radius:50%; font-size:12px; margin-right:6px; }}
  .ord.new {{ background:#9aa; }}
  .minbox {{ max-width:90px; }}
</style></head><body>
<h1>📊 보험 뉴스 다이제스트 설정</h1>
<div class="sub">값을 바꾸고 <b>[반영]</b> 을 누르면 GitHub에 저장되어 <b>익일 오전 7시 뉴스부터</b> 적용됩니다.</div>
{banner}
<form method="post">
  <input type="hidden" name="section_count" value="{total}">

  <fieldset><legend>🗂 대구분 섹션 (위→아래 순서로 다이제스트에 표시)</legend>
    <div class="hint">기사를 주제별로 묶어 섹션마다 <b>최소~최대</b> 건수로 정리합니다. 키워드는 제목을 우선 매칭하며,
      위쪽 섹션이 먼저 배정됩니다(우선순위). 키워드를 비운 섹션은 <b>기타</b>가 되어 나머지 기사를 모두 담습니다(맨 아래 권장).
      이름을 비우면 그 섹션은 삭제됩니다.</div>
    {sec_html}
  </fieldset>

  <fieldset><legend>📌 핀 지정 회사 (반드시 포함)</legend>
    <label>회사명 (한 줄에 하나)<textarea name="pinned_companies" rows="3">{esc(chr(10).join(s.get('pinned_companies',[])))}</textarea></label>
    <label class="minbox">최대 보장 건수<input type="number" min="0" name="pinned_max" value="{esc(s.get('pinned_max',2))}"></label>
  </fieldset>

  <fieldset><legend>🔎 검색 키워드 (네이버 뉴스 검색어)</legend>
    <div class="hint">한 줄에 하나. 많을수록 수집 범위가 넓어집니다.</div>
    <textarea name="naver_search_queries" rows="8">{esc(chr(10).join(s.get('naver_search_queries',[])))}</textarea>
  </fieldset>

  <fieldset><legend>🚫 제외 키워드 (노이즈 제거)</legend>
    <div class="hint">제목에 이 단어가 있으면 제외됩니다 (핀 회사 기사는 예외). 한 줄에 하나.</div>
    <textarea name="exclude_keywords" rows="6">{esc(chr(10).join(s.get('exclude_keywords',[])))}</textarea>
  </fieldset>

  <fieldset><legend>⭐ 중요도 가중치 (제목 포함 시 가산점)</legend>
    <div class="hint">형식: <code>키워드: 점수</code> (한 줄에 하나). 점수가 높을수록 상위 노출됩니다.</div>
    <textarea name="importance_keywords" rows="10">{esc(imp)}</textarea>
  </fieldset>

  <div class="bar">
    <button class="apply" formaction="/apply">✅ 반영 (저장 & 배포)</button>
    <button class="preview" formaction="/preview">👁 지금 미리보기 발송</button>
  </div>
</form>
</body></html>"""


def _open_browser():
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    Timer(1.0, _open_browser).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
