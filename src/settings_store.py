# -*- coding: utf-8 -*-
"""settings.json 읽기·쓰기와 GitHub 배포.

원래 dashboard.py 안에 있던 로직입니다. 정보사이트(webapp.py)의
관리자모드 → 뉴스·텔레그램 설정 화면이 이 모듈을 사용합니다.
"""

from __future__ import annotations

import json
import os
import re
import subprocess

import requests

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_PATH = os.path.join(APP_DIR, "settings.json")
INSURERS_PATH = os.path.join(APP_DIR, "data", "insurers.json")


# ─────────────────────── 뉴스 설정 ───────────────────────

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


# ─────────────────────── 보험사 데이터 ───────────────────────

def load_insurers() -> dict:
    with open(INSURERS_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_insurers(data: dict) -> None:
    with open(INSURERS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─────────────────────── 폼 파싱 ───────────────────────

def lines(text: str) -> list[str]:
    return [x.strip() for x in (text or "").splitlines() if x.strip()]


def terms(text: str) -> list[str]:
    """줄바꿈/콤마 모두 구분자로 인정."""
    return [x.strip() for x in re.split(r"[\n,]", text or "") if x.strip()]


def parse_importance(text: str) -> dict:
    out = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, val = line.rsplit(":", 1)
        try:
            out[key.strip()] = int(val.strip())
        except ValueError:
            continue
    return out


def as_int(val, default: int) -> int:
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return default


def as_float(val, default):
    try:
        return float(str(val).strip())
    except (ValueError, TypeError):
        return default


def parse_news_form(form) -> dict:
    sections = []
    for i in range(as_int(form.get("section_count"), 0)):
        name = (form.get(f"sec_name_{i}") or "").strip()
        if not name:
            continue
        sections.append({
            "name": name,
            "min": max(0, as_int(form.get(f"sec_min_{i}"), 3)),
            "max": max(1, as_int(form.get(f"sec_max_{i}"), 5)),
            "terms": terms(form.get(f"sec_terms_{i}")),
        })
    return {
        "naver_search_queries": lines(form.get("naver_search_queries")),
        "exclude_keywords": lines(form.get("exclude_keywords")),
        "importance_keywords": parse_importance(form.get("importance_keywords")),
        "pinned_companies": lines(form.get("pinned_companies")),
        "pinned_max": max(0, as_int(form.get("pinned_max"), 2)),
        "sections": sections,
    }


# ─────────────────────── git / 워크플로우 ───────────────────────

def _git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=APP_DIR,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def git_commit_push(*paths: str, message: str = "Update via dashboard") -> tuple[bool, str]:
    """지정한 파일만 커밋·푸시. 리포가 아니면 로컬 저장만 했다고 알립니다."""
    if _git("rev-parse", "--git-dir").returncode != 0:
        return True, "로컬에 저장했습니다 (git 리포지토리가 아니라 배포는 건너뜀)."

    _git("add", *paths)
    if _git("diff", "--cached", "--quiet").returncode == 0:
        return True, "변경 사항이 없어 커밋을 건너뛰었습니다 (이미 최신)."

    commit = _git("commit", "-m", message)
    if commit.returncode != 0:
        return False, f"커밋 실패: {commit.stderr or commit.stdout}"

    push = _git("push", "origin", "main")
    if push.returncode != 0:
        return False, f"로컬 저장·커밋은 됐지만 푸시 실패: {push.stderr or push.stdout}"
    return True, "GitHub에 배포 완료 — 익일 오전 7시 뉴스부터 반영됩니다."


def _repo_slug() -> str:
    out = _git("remote", "get-url", "origin").stdout.strip()
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?\s*$", out)
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
    slug, token = _repo_slug(), _github_token()
    if not slug or not token:
        return False, "GitHub 정보를 찾지 못했습니다 (remote/자격증명 확인)."
    try:
        resp = requests.post(
            f"https://api.github.com/repos/{slug}/actions/workflows/daily.yml/dispatches",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            json={"ref": "main"},
            timeout=20,
        )
    except requests.RequestException as e:
        return False, f"실행 요청 실패: {type(e).__name__}"
    if resp.status_code == 204:
        return True, "미리보기 발송 요청됨 — 1~2분 뒤 텔레그램 채널을 확인하세요."
    return False, f"실행 실패: HTTP {resp.status_code} {resp.text[:200]}"
