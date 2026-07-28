# 보험업계 일일 뉴스 다이제스트

국내 생명·손해보험 뉴스를 매일 오전 7시(KST)에 자동 수집·요약해 텔레그램으로 발송합니다.
**전 과정 완전 무료** (네이버 API·Gemini 요약·텔레그램·GitHub Actions 모두 무료).

## 파이프라인

```
수집(네이버API·RSS) → 분류(생명/손해/공통)·중복제거 → 중요도 선별(10~15건) → Gemini 요약 → 텔레그램 발송
```

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

## 조정 포인트

- 검색 키워드 추가/변경: `config.py` 의 `NAVER_SEARCH_QUERIES`
- 회사 사전 보강: `LIFE_INSURERS` / `NONLIFE_INSURERS`
- 발송 건수: `MIN_ARTICLES` / `MAX_ARTICLES`
- 요약 품질↑: `SUMMARY_MODEL` 을 `gemini-2.5-flash` 로 (여전히 무료)
- 발송 시각: `daily.yml` 의 cron (UTC 기준)
