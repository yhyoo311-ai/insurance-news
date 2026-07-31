# 한국 보험사 정보 시스템

국내 생명·손해·재보험사 **37개사**를 히트맵으로 보고, 회사를 클릭하면
주가차트·주주·재무분석·최근 뉴스를 한 화면에서 확인하는 로컬 정보사이트입니다.
기존의 **보험 뉴스 텔레그램 다이제스트**는 관리자모드 안으로 들어왔습니다.
로컬에서도 돌고, **웹에 배포해 어디서나 로그인해 쓸 수도 있습니다** (→ 4장).

```
┌ 정보사이트 (/)                       ← 메인
│    히트맵 · 회사 패널
└ 관리자모드 (/admin)
     ├ 뉴스·텔레그램 설정   ← 기존 dashboard.py 기능 그대로
     └ 보험사 데이터        ← DART 갱신 버튼 + 재무·주주·K-ICS 편집
```

## 실행

```bash
pip install -r requirements-dashboard.txt   # 최초 1회
python webapp.py                            # 또는 정보사이트_실행.bat 더블클릭
```

- 히트맵 http://127.0.0.1:5000
- 관리자모드 http://127.0.0.1:5000/admin/news

> 기존 습관대로 `python dashboard.py` 를 실행해도 됩니다 — 같은 앱을 띄우고
> 뉴스·텔레그램 설정 화면을 바로 엽니다.

## 1. 정보사이트

### 히트맵

- **타일 크기** — `총자산`(기본) 또는 `시가총액` 토글
  - `총자산`: 상장·비상장 37개사를 같은 기준으로 비교 (권장)
  - `시가총액`: 상장 12개사만. 시세가 없는 비상장 25개사는 히트맵에서 빠지며
    화면에 그 사실을 표시합니다 (추정 지분가치를 만들어 넣지 않습니다)
- **타일 색** — 전일 대비 등락률. 파랑(하락) ↔ 회색(보합) ↔ 빨강(상승) 7구간.
  비상장사는 색이 아니라 **`비상장` 라벨**로 구분합니다
- **분야 그룹** — `01 생명보험` `02 손해보험` `03 재보험·보증`.
  그룹 상자 면적은 실제 합계에 비례합니다. 그래서 재보험·보증(업계 총자산의 2% 남짓)처럼
  작은 분야는 읽을 수 없는 띠가 되므로, **그 그룹만 균등폭 칩으로 바꾸고 헤더에 밝힙니다**
- **표로 보기** — 색에 의존하지 않고 모든 값을 읽는 표 (히트맵과 같은 데이터)
- **통화** — KRW / USD (Yahoo Finance 환율)

### 회사 패널 (타일 클릭)

| 영역 | 내용 |
|------|------|
| 현재가 | 주가 + 전일 대비. 비상장사는 '비상장' 안내와 상장 모회사 참고 시세 |
| 주가 차트 | 최근 60거래일 종가. 마우스를 올리면 크로스헤어 + 날짜·종가 |
| 재무 분석 | 시가총액 · 자산총계 · 부채총계 · 자본총계 · 보험계약부채 · 영업이익 · 당기순이익 · PER · PBR · ROE · K-ICS · 52주 고저. 제목에 `2025 사업보고서 · 별도 (DART)` 처럼 출처·기준 표기 |
| 주요 주주 | 이름 · 지분율 · 구분 (최대주주 현황 + 5% 이상 대량보유, 지분율 순) |
| 최근 주요 뉴스 | 회사명이 **제목에** 있는 최신 기사 3건 |
| 출처 | Yahoo Finance / **DART 공시 원문 링크** / 네이버 뉴스 |

주소창에 `#c=<회사id>` 가 붙으므로 **그 주소를 복사하면 특정 회사 패널을 바로 열 수 있습니다.**

### 데이터 출처 — 무엇을 믿을 수 있나

| 항목 | 출처 | 신뢰도 |
|------|------|--------|
| 주가 · 전일대비 · 시가총액 · 52주 고저 · 주가차트 | Yahoo Finance (키 불필요, 15분 캐시) | 실측값 |
| 자산총계 · 부채총계 · 자본총계 · 영업이익 · 당기순이익 · 보험계약부채 | **DART 전자공시 사업보고서** | 공시값 (24개사) |
| 주요 주주 | **DART 최대주주 현황 + 5% 이상 대량보유 보고** | 공시값 (24개사) |
| 최근 주요 뉴스 | 네이버 뉴스 검색 API | 실측값 |
| PER · PBR · ROE | 시가총액 ÷ 위 재무값으로 계산 | **추정치** |
| K-ICS 비율 | 관리자모드 직접 입력 | **DART 에 없는 감독지표** |

각 회사 패널의 **출처** 항목에서 그 회사의 **DART 공시 원문으로 바로** 갈 수 있습니다.
재무는 회사마다 **별도/연결** 중 어느 기준인지 패널에 표기합니다 (별도 우선, 없으면 연결).

**DART 정기보고서를 제출하지 않는 13개사**는 재무가 개략치로 남습니다 —
메트라이프 · IBK연금 · iM라이프 · 라이나 · AIA · 하나생명 · 처브라이프 ·
교보라이프플래닛 · AXA손보 · MG손보 · 하나손보 · 캐롯 · 카카오페이손보.
증권을 발행하지 않아 사업보고서 의무가 없고 **감사보고서만** 냅니다.
이 회사들은 패널·관리자모드에 `개략치` 로 표시되고, 감사보고서 원문 링크가 붙습니다 —
링크를 열어 값을 확인하고 관리자모드에서 채운 뒤 **검증** 을 체크하세요.

상장 12개사 티커는 Yahoo Finance 에서 실제 조회해 확인했습니다.
메리츠화재는 2023년 지주 주식교환으로 **상장폐지** 되어 비상장으로 두고
메리츠금융지주(138040.KS) 시세를 참고로 함께 보여줍니다.

## 2. 관리자모드 · 뉴스·텔레그램 설정

매일 07:00(KST) 텔레그램으로 나가는 다이제스트를 조절합니다. 기존 대시보드와 동일합니다.

- 대구분 섹션(순서·건수·키워드) · 검색어 · 제외어 · 중요도 가중치 · 핀 회사 편집
- **[✅ 반영]** → `settings.json` 저장 + GitHub 커밋·푸시 → **익일 오전 7시부터 적용**
- **[👁 지금 미리보기 발송]** → 저장·배포 후 클라우드를 즉시 실행해 채널로 전송

제외 키워드는 **정보사이트의 회사별 뉴스에도 함께 적용**됩니다.

## 3. DART 재무·주주 갱신

```bash
python sync_dart.py            # 미리보기 (파일 안 바꿈, 변경 전/후 비교 출력)
python sync_dart.py --write    # 반영    (또는 DART갱신.bat 더블클릭)
python sync_dart.py --write --only samsung-life,kyobo-life
```

관리자모드 → 보험사 데이터 화면의 **[DART 전체 갱신]** 버튼으로도 같은 일을 합니다.

- 사업보고서(11011)의 **자산총계·부채총계·자본총계·영업이익·당기순이익·보험계약부채**와
  **최대주주 현황 · 5% 이상 대량보유**를 덮어씁니다
- 기준일(`as_of`)과 회사별 `별도/연결` 기준, DART 공시 원문 링크를 함께 기록합니다
- **K-ICS 비율과 티커는 건드리지 않습니다** — K-ICS 는 DART 에 없고,
  티커는 Yahoo 로 검증한 값이라 DART 의 오래된 `stock_code` 로 덮으면 안 됩니다
- 정기보고서 미제출 회사는 **기존 값을 그대로 두고** 감사보고서 링크만 채웁니다

DART 고유번호 매핑은 `add_dart_codes.py` 에 명시돼 있습니다 (1회성).
DART 는 약칭이 아니라 등기 상호를 쓰므로(메리츠화재 → `메리츠화재해상보험`,
KB라이프 → `케이비라이프생명보험`) 유사도 자동 매칭은 쓰지 않습니다 —
'삼성생명'이 지주회사 '삼성'과 100% 매칭되는 사고가 납니다.
스크립트는 저장 전에 37건의 등기 상호를 되짚어 검증합니다.

## 4. 웹 배포 — 어디서나 접속 (전액 무료)

```
GitHub Actions (백엔드)                      Cloudflare (프론트)
  ├ site.yml       평일 09~16:30 30분마다  ──직접 업로드──▶  Pages ──▶ 주소 발급
  │                Yahoo·네이버 조회 → dist/                    │
  ├ sync-dart.yml  DART 재무·주주 → 커밋                        └ Access (이메일 OTP 로그인)
  └ daily.yml      매일 07시 텔레그램 다이제스트

저장소   = GitHub 리포 (settings.json · data/insurers.json)
웹 관리자 = 브라우저가 GitHub API 로 직접 커밋 (서버 없음)
```

**서버가 없습니다.** 그래서 잠들지 않고(콜드스타트 0초) 요금도 0원입니다.
주가는 최대 30분 지연되며 화면에서 [사이트 지금 갱신]으로 강제 갱신할 수 있습니다.

### 왜 이 구조인가

무료 호스팅은 대부분 파일시스템이 휘발성이라 설정을 저장할 곳이 없습니다.
그런데 이 프로젝트는 이미 **GitHub 의 `settings.json` 을 다이제스트가 읽고** 있습니다.
그래서 GitHub 를 그대로 데이터베이스로 쓰고, 웹 관리자는 브라우저에서
GitHub Contents API 로 커밋합니다. 서버·DB 를 새로 두지 않아도 기존 파이프라인이 그대로 돕니다.

### 설치 (한 번만, 약 20분)

> **순서 주의** — ②③④(Cloudflare 준비 + Secrets 등록)를 **먼저** 끝내고 ①(푸시)을 하세요.
> Secrets 없이 푸시하면 `site.yml` 이 자동 실행돼 업로드 단계에서 실패합니다
> (무해하지만 Actions 에 빨간 표시가 남습니다). 이미 푸시했다면 ④까지 마친 뒤
> Actions 에서 Run workflow 로 다시 돌리면 됩니다.

**① 리포에 코드·데이터 올리기**

```bash
git add -A
git commit -m "정보사이트 + 웹 관리자 + DART 연동"
git push
```

`data/insurers.json` 이 반드시 올라가야 합니다 (사이트 데이터의 원본).
`dist/` 와 `.cache/` 는 `.gitignore` 로 제외됩니다 — Actions 가 매번 새로 굽습니다.

**② Cloudflare Pages 프로젝트 만들기**

1. [dash.cloudflare.com](https://dash.cloudflare.com) 가입 (무료, 카드 불필요)
2. **Workers & Pages → Create → Pages → Upload assets**
3. 프로젝트 이름 **`insuranceinfo`** — 워크플로우에 이 이름이 박혀 있습니다.
   다르게 하려면 `.github/workflows/site.yml` 의 `--project-name` 도 함께 바꾸세요
4. 아무 파일이나 하나 올려 프로젝트를 만들어 둡니다 (이후엔 Actions 가 덮어씁니다)
5. 발급된 주소 확인: `https://insuranceinfo.pages.dev`

**③ Cloudflare API 토큰 발급**

My Profile → API Tokens → Create Token → **Custom token**

- Permissions: **Account · Cloudflare Pages · Edit**
- Account Resources: 본인 계정

만들어진 토큰과, 대시보드에 표시되는 **Account ID** 를 복사해 둡니다.

**④ GitHub Secrets 등록**

리포 → Settings → Secrets and variables → Actions → New repository secret

| 이름 | 값 |
|------|-----|
| `CLOUDFLARE_API_TOKEN` | ③에서 만든 토큰 |
| `CLOUDFLARE_ACCOUNT_ID` | ③의 Account ID |
| `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | 이미 등록돼 있음 |
| `DART_API_KEY` | DART 인증키 — `sync-dart.yml` 용, **새로 등록 필요** |

**⑤ 첫 배포**

리포 → Actions → **정보사이트 배포 (Cloudflare Pages)** → Run workflow.
2~3분 뒤 `https://insuranceinfo.pages.dev` 에서 열립니다.

**⑥ 로그인 걸기 (비밀번호 게이트 — 나만 보기)**

Cloudflare → **Workers & Pages → insuranceinfo → Settings → Variables and Secrets**

| 항목 | 값 |
|------|-----|
| 이름 | `SITE_PASSWORD` |
| 타입 | **Secret** (Text 아님 — Text 는 대시보드에 그대로 보입니다) |
| 값 | 원하는 비밀번호. 대입 공격에 버티도록 **길게** |
| 환경 | **Production** (Preview 도 쓰면 함께 추가) |

저장하면 접속 시 비밀번호를 묻고, 맞으면 30일짜리 서명 쿠키가 발급됩니다.
`SITE_PASSWORD` 를 바꾸면 기존 세션은 전부 무효가 됩니다. 로그아웃은 `/__logout`.

> **Cloudflare Access 는 이 프로젝트에 쓸 수 없습니다.** Access 는 본인 계정에 등록된
> 도메인(zone)에만 걸립니다. `pages.dev` 는 Cloudflare 소유 공용 도메인이라 대상이
> 되지 않습니다. 그래서 사이트 자체가 인증합니다 — `gate/_worker.js` 참고.
> 도메인을 사서 Cloudflare 에 등록하면 그때는 Access(이메일 OTP)로 바꿀 수 있습니다.

> `SITE_PASSWORD` 를 설정하기 전까지는 **아무도** 열 수 없습니다(503). 설정을 깜빡한 채
> 배포됐을 때 무방비로 열리는 것보다 안전한 쪽으로 정했습니다.

**⑦ 웹 관리자용 GitHub 토큰**

`https://insuranceinfo.pages.dev/admin/` 에 들어가면 토큰을 요청합니다.
[Fine-grained token 만들기](https://github.com/settings/personal-access-tokens/new) →
Repository access 를 **Only select repositories** 로 이 리포만 선택 →
Permissions 에서 **Contents: Read and write** + **Actions: Read and write** 두 개만 켜기.

토큰은 그 브라우저의 localStorage 에만 저장되고 github.com 외 어디로도 전송되지 않습니다.
공용 PC 에서 썼다면 [토큰 삭제] 를 눌러 주세요.

### 웹 관리자에서 할 수 있는 일

| 탭 | 기능 | 반영 시점 |
|----|------|-----------|
| 뉴스·텔레그램 설정 | 섹션·검색어·제외어·가중치·핀 회사 편집 → `settings.json` 커밋 | 익일 07시 다이제스트 |
| 보험사 데이터 | 재무·주주·티커·K-ICS 편집 → `data/insurers.json` 커밋 | 커밋 즉시 사이트 자동 재배포 |
| 배포·갱신 | [사이트 지금 갱신] · [DART 전체 갱신] · [지금 미리보기 발송] + 최근 실행 현황 | 1~2분 |

로컬 `python webapp.py` 도 그대로 씁니다 — 표 편집은 로컬이 편하고, 웹은 어디서나 됩니다.

### 자동 실행 일정

| 워크플로우 | 주기 |
|-----------|------|
| `site.yml` | 평일 KST 09:00~16:30 30분마다 + 매일 07:20 + `data/`·`static/`·`templates/` 푸시 시 |
| `sync-dart.yml` | 매월 5일 KST 10:00 (+ 관리자 버튼) |
| `daily.yml` | 매일 KST 07:00 텔레그램 발송 (기존과 동일) |

공개 리포라 Actions 사용량은 **무제한 무료**입니다. Cloudflare Pages 는 무료 플랜에서
요청 수 제한이 없고 배포가 월 500회까지인데, 위 일정은 월 약 350회입니다.

### 스냅샷을 손으로 굽기 (선택)

Actions 없이 로컬에서 만들어 아무 곳에나 올릴 수도 있습니다.

```bash
python build_static.py --open      # 또는 스냅샷_빌드.bat 더블클릭
→ dist/index.html        정보사이트 (CSS·JS·데이터 인라인)
→ dist/admin/index.html  웹 관리자
```

API 키는 들어가지 않습니다 — 빌드 시점에 조회한 **결과만** 담습니다.
주가는 구운 시점 값으로 고정되므로 최신 시세가 필요하면 다시 빌드하세요.

### 다른 무료 대안 (참고)

| 방식 | 장점 | 단점 |
|------|------|------|
| **GitHub Pages** | 설정이 가장 단순 | 공개 리포에선 **비공개 불가** (로그인 못 걸음) |
| **Netlify** | 드래그 배포 | 비밀번호 보호가 유료 플랜 |
| **Render (Flask 그대로)** | 실시간 조회 | 15분 뒤 잠들어 **첫 진입 30~60초**, 파일시스템 휘발성 |

"로그인해야 보기" 조건에서는 Cloudflare Pages + Access 가 유일하게 완전 무료입니다.

## 파일 구조

| 파일 | 역할 |
|------|------|
| `webapp.py` | Flask 앱 — 정보사이트 + 관리자모드 라우트 |
| `data/insurers.json` | **보험사 마스터** (37개사: 티커·분야·재무·주주) |
| `src/market.py` | Yahoo Finance 시세·시가총액·환율 + PER·PBR·ROE 파생 |
| `src/dart.py` | **DART 전자공시** 재무·주주·공시원문 링크 (비상장사 포함) |
| `sync_dart.py` | DART 값으로 `insurers.json` 갱신 (미리보기 / `--write`) |
| `add_dart_codes.py` | DART 고유번호 매핑 부여 (1회성, 등기 상호 검증 포함) |
| `src/console.py` | cp949 콘솔에서 print 크래시 방지 |
| `src/company_news.py` | 회사별 뉴스 (제목 매칭·묶음기사 후순위·같은사건 중복제거) |
| `src/settings_store.py` | settings.json / insurers.json 읽기·쓰기 + git 배포 |
| `templates/` | `_site.html`(히트맵 본문, 로컬·스냅샷 공용) · `admin_*.html` |
| `static/css/app.css` | 색 팔레트(검증된 diverging 램프) · 레이아웃 · 라이트/다크 |
| `static/js/app.js` | squarified treemap · 회사 패널 · SVG 차트 · 표 보기 |
| `build_static.py` | `dist/index.html` + `dist/admin/index.html` 빌드 |
| `templates/admin_static.html` · `static/js/admin.js` | **웹 관리자** (서버 없이 GitHub API 로 커밋) |
| `.github/workflows/site.yml` | 스냅샷 빌드 → Cloudflare Pages 업로드 (30분 주기) |
| `.github/workflows/sync-dart.yml` | DART 갱신 → `data/insurers.json` 커밋 |
| `dashboard.py` | (구) 진입점 — webapp 의 관리자모드로 리다이렉트 |
| `main.py` · `src/collect,filters,classify,rank,summarize,notify.py` | 매일 07시 텔레그램 다이제스트 파이프라인 (변경 없음) |
| `.github/workflows/daily.yml` | 매일 07:00 KST 자동 실행 |

`.cache/`(시세·뉴스 캐시)와 `dist/`(스냅샷)는 git에서 제외됩니다.

## 환경변수

| 키 | 쓰는 곳 | 없으면 |
|----|---------|--------|
| `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | 다이제스트 + 회사별 뉴스 | 뉴스 영역이 비고 안내 문구 표시 |
| `GEMINI_API_KEY` | 다이제스트 요약 | 다이제스트만 영향 |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | 다이제스트 발송 | 다이제스트만 영향 |
| `DART_API_KEY` | 재무·주주 갱신 (`sync_dart.py`) | 갱신 불가, 기존 값으로 동작 |

주가·시가총액·환율은 **키가 필요 없습니다.**
`DART_API_KEY` 는 https://opendart.fss.or.kr 에서 무료 발급합니다 (일 20,000건).

## 알려진 한계

- 같은 보도자료를 받아쓴 기사는 제목·수치·첫 단어로 걸러내지만 **완벽하지 않습니다.**
  표현이 크게 다른 재작성 기사는 중복으로 남을 수 있습니다.
- 제목에 회사명이 없는 기사는 쓰지 않습니다. 그래서 그날 단독 보도가 없는 회사는
  뉴스가 3건보다 적거나 0건일 수 있습니다 (억지로 채우면 무관한 기사가 올라옵니다).
- `시가총액` 기준 히트맵은 상장사만 담습니다.
- DART 정기보고서 미제출 13개사는 재무가 개략치입니다 (감사보고서 원문 링크 제공).
- 대량보유 보고의 지분율은 **특별관계자 합산**입니다. 최대주주 측과 겹치지 않도록
  이름을 정규화해(`삼성물산` = `삼성물산(주)`) 중복 계상을 막지만, 표기가 크게 다르면
  같은 주주가 두 줄로 남을 수 있습니다.
- 비상장사의 주가차트 자리에는 상장 모회사 시세가 **참고로만** 표시됩니다.
