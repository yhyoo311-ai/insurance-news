# Genie's Insurance Note

국내 생명·손해·재보험사 **35개사**를 히트맵으로 보고, 회사를 클릭하면
주가차트·주주·재무분석·최근 뉴스를 한 화면에서 확인하는 로컬 정보사이트입니다.
기존의 **보험 뉴스 텔레그램 다이제스트**는 관리자모드 안으로 들어왔습니다.
로컬에서도 돌고, **웹에 배포해 어디서나 로그인해 쓸 수도 있습니다** (→ 4장).

```
┌ 정보사이트 (/)                       ← 메인
│    히트맵 · 회사 패널
└ 관리자모드 (/admin)
     ├ 뉴스·텔레그램 설정   ← 기존 dashboard.py 기능 그대로
     └ 보험사 데이터        ← DART·FISIS 갱신 버튼 + 재무·주주·K-ICS 편집
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
  - `총자산`: 상장·비상장 35개사를 같은 기준으로 비교 (권장)
  - `시가총액`: 상장 12개사만. 시세가 없는 비상장 25개사는 히트맵에서 빠지며
    화면에 그 사실을 표시합니다 (추정 지분가치를 만들어 넣지 않습니다)
- **타일 색** — 전일 대비 등락률. 파랑(하락) ↔ 회색(보합) ↔ 빨강(상승) 7구간.
  비상장사는 색이 아니라 **`비상장` 라벨**로 구분합니다
- **분야 그룹** — `01 생명보험` `02 손해보험` `03 재보험·보증`.
  그룹 상자 면적은 실제 합계에 비례합니다. 그래서 재보험·보증(업계 총자산의 2% 남짓)처럼
  작은 분야는 읽을 수 없는 띠가 되므로, **그 그룹만 균등폭 칩으로 바꾸고 헤더에 밝힙니다**
- **표로 보기** — 색에 의존하지 않고 모든 값을 읽는 표 (히트맵과 같은 데이터).
  머리글을 누르면 정렬되고 K-ICS 열이 함께 있습니다
- **회사 검색** — 이름·영문명·티커로 좁힙니다. `/` 로 어디서나 검색창에 포커스가 오고
  Enter 로 첫 결과를 엽니다. 검색어에 안 걸린 타일은 **지우지 않고 흐리게** 합니다
  (지우면 면적 비례가 깨져 '전체 중 어디쯤'을 잃습니다)
- **요약 지표** — 상단에 업계 총자산 · 회사 수 · 오늘 등락 · K-ICS 중앙값 · 기준일.
  K-ICS 는 평균이 아니라 **중앙값**입니다 (규모 차이가 커서 단순평균은 소형사에 끌려갑니다)
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
| 〃 (증권 미발행사) | **FISIS 업무보고서** (금융감독원) | 감독제출값 (11개사) |
| 주요 주주 | **DART 최대주주 현황 + 5% 이상 대량보유 보고** | 공시값 (24개사) |
| 최근 주요 뉴스 | 네이버 뉴스 검색 API | 실측값 |
| PER · PBR · ROE | 시가총액 ÷ 위 재무값으로 계산 | **추정치** |
| K-ICS 비율 | FISIS 업무보고서 | **감독제출값 · 경과조치 기준 표기** |

각 회사 패널의 **출처** 항목에서 그 회사의 **DART 공시 원문으로 바로** 갈 수 있습니다.
재무는 회사마다 **별도/연결** 중 어느 기준인지 패널에 표기합니다 (별도 우선, 없으면 연결).

**DART 정기보고서를 제출하지 않는 11개사**(메트라이프 · IBK연금 · iM라이프 · 라이나 ·
AIA · 하나생명 · 처브라이프 · 교보라이프플래닛 · AXA손보 · 하나손보 · 카카오페이손보)는
증권을 발행하지 않아 사업보고서 의무가 없습니다. 이 회사들의 재무는 **FISIS 업무보고서**
값으로 채우고 패널에 `업무보고서 · 감독회계 (FISIS)` 라고 표기합니다.

> **두 기준이 섞여 있습니다.** 자산총계는 두 출처가 원 단위까지 같지만, 부채·자본 배분은
> 감독회계와 IFRS 별도재무제표가 달라 회사에 따라 차이가 납니다
> (삼성생명 자본 DART 56.4조 / FISIS 43.6조). 자산총계 비교는 유효하지만
> **자본총계를 회사 간에 비교할 때는 기준을 확인**하세요.

상장 12개사 티커는 Yahoo Finance 에서 실제 조회해 확인했습니다.
메리츠화재는 2023년 지주 주식교환으로 **상장폐지** 되어 비상장으로 두고
메리츠금융지주(138040.KS) 시세를 참고로 함께 보여줍니다.

## 2. 관리자모드 · 뉴스·텔레그램 설정

매일 07:00(KST) 텔레그램으로 나가는 다이제스트를 조절합니다. 기존 대시보드와 동일합니다.

- 대구분 섹션(순서·건수·키워드) · 검색어 · 제외어 · 중요도 가중치 · 핀 회사 편집
- **[✅ 반영]** → `settings.json` 저장 + GitHub 커밋·푸시 → **익일 오전 7시부터 적용**
- **[👁 지금 미리보기 발송]** → 저장·배포 후 클라우드를 즉시 실행해 채널로 전송

제외 키워드는 **정보사이트의 회사별 뉴스에도 함께 적용**됩니다.

## 3. 재무·주주·K-ICS 갱신

### DART — 사업보고서 재무·주주

```bash
python sync_dart.py            # 미리보기 (파일 안 바꿈, 변경 전/후 비교 출력)
python sync_dart.py --write    # 반영    (또는 DART갱신.bat 더블클릭)
python sync_dart.py --write --only samsung-life,kyobo-life
```

관리자모드 → 보험사 데이터 화면의 **[DART 전체 갱신]** 버튼으로도 같은 일을 합니다.

- 사업보고서(11011)의 **자산총계·부채총계·자본총계·영업이익·당기순이익·보험계약부채**와
  **최대주주 현황 · 5% 이상 대량보유**를 덮어씁니다
- 기준일(`as_of`)과 회사별 `별도/연결` 기준, DART 공시 원문 링크를 함께 기록합니다
- **K-ICS 비율과 티커는 건드리지 않습니다** — K-ICS 는 `sync_fisis.py` 담당이고,
  티커는 Yahoo 로 검증한 값이라 DART 의 오래된 `stock_code` 로 덮으면 안 됩니다
- 정기보고서 미제출 회사는 **기존 값을 그대로 두고** 감사보고서 링크만 채웁니다

DART 고유번호 매핑은 `add_dart_codes.py` 에 명시돼 있습니다 (1회성).
DART 는 약칭이 아니라 등기 상호를 쓰므로(메리츠화재 → `메리츠화재해상보험`,
KB라이프 → `케이비라이프생명보험`) 유사도 자동 매칭은 쓰지 않습니다 —
'삼성생명'이 지주회사 '삼성'과 100% 매칭되는 사고가 납니다.
스크립트는 저장 전에 37건의 등기 상호를 되짚어 검증합니다.

### FISIS — K-ICS 와 증권 미발행사 재무

```bash
python sync_fisis.py            # 미리보기 (파일 안 바꿈)
python sync_fisis.py --write    # 반영
python sync_fisis.py --write --base 202512
```

관리자모드 → 보험사 데이터 화면의 **[K-ICS·감독통계 갱신]** 버튼으로도 같은 일을 합니다.

[FISIS(금융감독원 금융통계정보시스템)](https://fisis.fss.or.kr) 은 보험사가 감독당국에
**매분기 내는 업무보고서**에서 뽑은 통계입니다. DART 와 달리 상장·비상장을 가리지 않아
사업보고서를 내지 않는 회사도 조회됩니다.

- **K-ICS 비율 — 전 회사.** DART 에 없는 감독지표라 여기가 유일한 출처입니다
- **증권 미발행사 재무만** 채웁니다. DART 로 검증된 회사는 건드리지 않습니다 —
  두 기준을 한 화면에 섞으면 회사 간 비교가 깨지기 때문입니다
- **경과조치** 적용 여부에 따라 K-ICS 가 달라집니다. 신청하지 않은 회사는 '적용 후'가
  `0` 으로 오므로, 적용 후가 0보다 크면 그 값을 쓰고 아니면 적용 전을 쓴 뒤
  어느 쪽인지 패널에 표기합니다
- **손익은 분기 단독값**이라 연간을 만들려면 4개 분기를 더합니다. 한 분기라도 비면
  합계를 쓰지 않고 비워 둡니다 (반쪽 숫자를 연간값처럼 보이게 하지 않기 위해)

FISIS 회사코드 매핑은 `add_fisis_codes.py` 에 명시돼 있습니다 (1회성).
여기서도 자동 매칭은 쓰지 않습니다 — 이름 유사도로 맞추면 `하나생명보험` 과
`하나손해보험` 이 서로 붙습니다. 저장 전에 35건의 상호와 권역을 되짚어 검증합니다.

## 4. 웹 배포 — 어디서나 접속 (전액 무료)

```
GitHub Actions (백엔드)                      Cloudflare (프론트)
  ├ site.yml       평일 09~16:30 30분마다  ──직접 업로드──▶  Pages ──▶ 주소 발급
  │                Yahoo·네이버 조회 → dist/                    │
  ├ sync-dart.yml  DART 재무·주주 → 커밋                        └ _worker.js (비밀번호 게이트)
  ├ sync-fisis.yml K-ICS·감독통계 → 커밋
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
| `DART_API_KEY` | DART 인증키 — `sync-dart.yml` 용 |
| `FISIS_API_KEY` | FISIS 인증키 — `sync-fisis.yml` 용 ([발급](https://fisis.fss.or.kr)) |

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

> **배포별 주소 주의.** Pages 는 배포마다 `<해시>.insuranceinfo.pages.dev` 를 발급하고
> 그 주소는 계속 살아 있습니다. 게이트가 없던 시절의 배포는 새로 배포해도 막히지 않으니
> **Deployments 목록에서 삭제**해야 닫힙니다 (게이트 도입 시 2건을 지웠습니다).

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
| 〃 | **[K-ICS·감독통계 갱신]** 버튼 → `sync-fisis.yml` 실행 | 1~2분 |
| 배포·갱신 | [사이트 지금 갱신] · [DART 전체 갱신] · [지금 미리보기 발송] + 최근 실행 현황 | 1~2분 |

로컬 `python webapp.py` 도 그대로 씁니다 — 표 편집은 로컬이 편하고, 웹은 어디서나 됩니다.

### 자동 실행 일정

| 워크플로우 | 주기 |
|-----------|------|
| `site.yml` | 평일 KST 09:00~16:30 30분마다 + 매일 07:20 + `data/`·`static/`·`templates/` 푸시 시 |
| `sync-dart.yml` | 매월 5일 KST 10:00 (+ 관리자 버튼) |
| `sync-fisis.yml` | 매월 5일 KST 11:00 (+ 관리자 버튼) |
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
| `data/insurers.json` | **보험사 마스터** (35개사: 티커·분야·재무·주주·K-ICS) |
| `src/market.py` | Yahoo Finance 시세·시가총액·환율 + PER·PBR·ROE 파생 |
| `src/dart.py` | **DART 전자공시** 재무·주주·공시원문 링크 (비상장사 포함) |
| `sync_dart.py` | DART 값으로 `insurers.json` 갱신 (미리보기 / `--write`) |
| `add_dart_codes.py` | DART 고유번호 매핑 부여 (1회성, 등기 상호 검증 포함) |
| `src/fisis.py` | **FISIS 감독통계** K-ICS·증권 미발행사 재무 |
| `sync_fisis.py` | FISIS 값으로 K-ICS 전 회사 + 미발행사 재무 갱신 |
| `add_fisis_codes.py` | FISIS 회사코드 매핑 + 소멸사 제거 (1회성, 상호·권역 검증) |
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
| `.github/workflows/sync-fisis.yml` | K-ICS·감독통계 갱신 → 커밋 |
| `gate/_worker.js` | 비밀번호 게이트 — Pages 앞단에서 모든 요청 검사 |
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
| `FISIS_API_KEY` | K-ICS·감독통계 갱신 (`sync_fisis.py`) | 갱신 불가, 기존 값으로 동작 |
| `SITE_PASSWORD` | 웹 배포판 접근 (Cloudflare Pages 환경변수) | **전 요청 503 차단** |

주가·시가총액·환율은 **키가 필요 없습니다.**
`DART_API_KEY` 는 https://opendart.fss.or.kr 에서 무료 발급합니다 (일 20,000건).
`FISIS_API_KEY` 는 https://fisis.fss.or.kr 에서 무료 발급합니다.
`SITE_PASSWORD` 는 `.env` 가 아니라 **Cloudflare Pages 환경변수**로 넣습니다 (4장 ⑥).

## 알려진 한계

- 같은 보도자료를 받아쓴 기사는 제목·수치·첫 단어로 걸러내지만 **완벽하지 않습니다.**
  표현이 크게 다른 재작성 기사는 중복으로 남을 수 있습니다.
- 제목에 회사명이 없는 기사는 쓰지 않습니다. 그래서 그날 단독 보도가 없는 회사는
  뉴스가 3건보다 적거나 0건일 수 있습니다 (억지로 채우면 무관한 기사가 올라옵니다).
- `시가총액` 기준 히트맵은 상장사만 담습니다.
- 재무 기준이 두 종류입니다 — DART 24개사는 IFRS 별도, FISIS 11개사는 감독회계.
- K-ICS 는 경과조치 적용 전·후가 섞여 있습니다 (35개사 중 28개사가 적용 후).
  회사마다 어느 기준인지 패널에 표기합니다.
- 대량보유 보고의 지분율은 **특별관계자 합산**입니다. 최대주주 측과 겹치지 않도록
  이름을 정규화해(`삼성물산` = `삼성물산(주)`) 중복 계상을 막지만, 표기가 크게 다르면
  같은 주주가 두 줄로 남을 수 있습니다.
- 비상장사의 주가차트 자리에는 상장 모회사 시세가 **참고로만** 표시됩니다.


## 서체

본문은 **KoPubWorld 돋움**입니다. CDN 이 아니라 `static/fonts/` 에 서브셋을 넣고
같은 출처에서 서비스합니다 — 사내망에서 외부 CDN 이 막혀도 글꼴이 깨지지 않습니다.

| 굵기 | 원본 | 서브셋 |
|------|------|--------|
| Light (300) | 1,864KB | 286KB |
| Medium (400) | 1,982KB | 323KB |
| Bold (700) | 2,008KB | 305KB |

한글 음절 **11,172자를 전부** 담았습니다. 자주 쓰는 2,350자만 남기면 드문 음절에서
시스템 폰트로 튀어 한 줄 안에서 서체가 섞입니다. 원본이 큰 건 일본어·한자 때문이고,
그쪽을 덜어내 90% 가까이 줄였습니다. 이모지는 서브셋에 없어 시스템 이모지로 넘어갑니다.

KoPub 돋움은 굵기가 **300/400/700 세 단계뿐**이라 500·600 은 쓰지 않습니다
(브라우저가 합성하거나 400 으로 떨어뜨려 굵기 위계가 무너집니다).

서브셋을 다시 만들려면:

```bash
pip install fonttools brotli
python -m fontTools.subset KoPubWorld-Dotum-Medium.woff2   --unicodes=U+0020-007E,U+00A0-00FF,U+2010-2027,U+2030-205E,U+20A9,U+20AC,U+2190-21FF,U+2500-257F,U+25A0-25CF,U+2713-2717,U+3000-303F,U+3200-32FF,U+AC00-D7A3,U+3130-318F,U+FF01-FF60   --flavor=woff2 --no-hinting --desubroutinize   --output-file=static/fonts/KoPubWorldDotum-Medium.woff2
```

원본은 npm 패키지 `font-kopubworld` 에 있습니다
(`https://cdn.jsdelivr.net/npm/font-kopubworld@1.0.3/fonts/`).

경로는 로컬 Flask 와 정적 스냅샷이 **`/fonts/...` 하나로 같습니다.**
스냅샷은 CSS 가 HTML 에 인라인돼 상대경로가 루트 기준이 되는데 Flask 는 CSS 가
`/static/css/` 에 있어 어긋나므로, Flask 쪽에 `/fonts/` 라우트를 두어 맞췄습니다.
비밀번호 게이트도 `/fonts/**.woff2` 만은 인증 없이 통과시킵니다
(로그인 화면을 같은 서체로 보이게 하려고 — 공개 배포 글꼴이라 새는 정보는 없습니다).
