# 보험업계 일일 뉴스 다이제스트

국내 생명·손해보험 뉴스를 매일 오전 7시(KST)에 자동 수집·요약해 텔레그램으로 발송합니다.
**전 과정 완전 무료** (네이버 API·Gemini 요약·텔레그램·GitHub Actions 모두 무료).

## 파이프라인

```
수집(네이버API·RSS) → 중복제거 → 대구분 섹션 배정 → 섹션별 상위 min~max건 선별 → Gemini 요약 → 텔레그램 발송
```

기사는 아래 대구분 섹션으로 묶여 섹션마다 3~5건씩 정리됩니다 (순서·건수·키워드는 대시보드에서 조절):
`기업 M&A·지배구조` · `소비자·분쟁·제재` · `규제·제도·정책` · `실적·재무·건전성` · `상품·영업·채널(GA)` · `기업 일반동향(해외진출 포함)`
각 기사에는 `[생명]`/`[손해]` 태그가 붙습니다.

## 파일 구조

| 파일 | 역할 |
|------|------|
| `config.py` | 키워드·회사 사전·소스·파라미터 |
| `src/collect.py` | 네이버 검색 API + RSS 수집 |
| `src/classify.py` | 생명/손해/공통 분류 + 같은 사건 중복 제거 |
| `src/rank.py` | 중요도 스코어링 → 상위 N건 |
| `src/summarize.py` | Gemini 무료 API 요약 (REST) |
| `src/notify.py` | 텔레그램 메시지 포맷·발송 |
| `main.py` | 파이프라인 오케스트레이션 |
| `get_chat_id.py` | 텔레그램 chat_id 확인 도구 |
| `.github/workflows/daily.yml` | 매일 07:00 KST 자동 실행 |

## 준비물 (환경변수)

| 키 | 발급처 |
|----|--------|
| `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | https://developers.naver.com → 애플리케이션 등록 → 검색 API |
| `GEMINI_API_KEY` | https://aistudio.google.com → Get API key (무료, 카드 불필요) |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 `@BotFather` → `/newbot` |
| `TELEGRAM_CHAT_ID` | `python get_chat_id.py` 로 확인 |

## 로컬 실행

```bash
pip install -r requirements.txt
cp .env.example .env      # 값 채우기
python get_chat_id.py     # chat_id 확인 (봇에게 메시지 1회 보낸 뒤)
python main.py            # 다이제스트 1회 발송
```

## 자동화 (GitHub Actions)

1. 이 폴더를 GitHub 리포지토리로 push
2. 리포 → Settings → Secrets and variables → Actions 에 위 5개 키 등록
3. Actions 탭에서 "보험 뉴스 다이제스트" → **Run workflow** 로 즉시 테스트
4. 이후 매일 07:00 KST 자동 실행

## 설정 대시보드 (키워드·비중 조절)

코드를 직접 고치지 않고 웹 화면에서 조절할 수 있습니다.

```bash
pip install -r requirements-dashboard.txt   # 최초 1회 (flask 설치)
python dashboard.py                          # 또는 대시보드_실행.bat 더블클릭
```

- 브라우저(http://127.0.0.1:5000)에서 대구분 섹션(순서·건수·키워드)·검색어·제외어·가중치·핀 회사를 편집
- **[✅ 반영]** → `settings.json` 저장 후 GitHub에 자동 커밋·푸시 → **익일 오전 7시 뉴스부터 적용**
- **[👁 지금 미리보기 발송]** → 저장·배포 후 클라우드를 즉시 실행해 채널로 바로 전송(결과 확인용)

> 조절값은 `settings.json` 에 저장되며, 파이프라인(`config.py`)이 이 파일을 우선 사용합니다.
> `settings.json` 이 없으면 `config.py` 의 기본값으로 동작합니다.

## 조정 포인트

- **대부분은 대시보드에서** 조절 (섹션·건수·키워드·가중치·핀 회사) → `settings.json` 에 저장
- 대구분 섹션 정의: `config.py` 의 `SECTIONS` (또는 대시보드의 "대구분 섹션")
- 회사 사전 보강: `config.py` 의 `LIFE_INSURERS` / `NONLIFE_INSURERS`
- 요약 품질↑: `SUMMARY_MODEL` 을 `gemini-2.5-flash` 로 (여전히 무료)
- 발송 시각: `daily.yml` 의 cron (UTC 기준)
