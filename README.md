# 🏠 Cron-Estate: 네이버부동산 매물 모니터링 봇

네이버부동산에서 관심 아파트 단지의 매매 매물을 자동으로 모니터링하고,
디스코드 채널에 실시간 알림을 보내주는 봇입니다.

## ✨ 주요 기능

- 🔍 **자동 스캔**: 30분 간격으로 네이버부동산 매물 자동 수집
- 🏠 **신규 매물 알림**: 새로운 매물이 등록되면 즉시 알림
- 📊 **가격 변동 감지**: 매물 가격이 변경되면 이전/현재 가격 비교 알림
- ✅ **매물 삭제 감지**: 매물이 사라지면 거래완료 추정 알림
- 📋 **중복 그룹핑**: 같은 물건에 여러 중개사 매물을 그룹으로 묶어 표시

## 📋 슬래시 커맨드

| 명령어 | 설명 |
|--------|------|
| `/매물` | 현재 모니터링 중인 매물 목록 (그룹별) |
| `/단지추가 검색어:` | 네이버부동산에서 단지 검색 후 모니터링 추가 |
| `/단지삭제 단지명:` | 모니터링 단지 제거 |
| `/단지목록` | 모니터링 중인 단지 목록 |
| `/가격이력 동: 호:` | 특정 호수의 가격 변동 이력 |
| `/스캔` | 수동 즉시 스캔 |

## 🚀 설치 및 실행

### 1. 사전 준비

- Python 3.12 이상
- Discord 봇 토큰 ([Discord Developer Portal](https://discord.com/developers/applications)에서 생성)

### 2. 프로젝트 설정

```bash
# 프로젝트 클론
git clone <repo-url>
cd cron-estate

# 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 3. 환경 변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 열어 값을 설정:

```env
DISCORD_TOKEN=여기에_디스코드_봇_토큰_입력
CHANNEL_ID=여기에_디스코드_채널_ID_입력
```

### 4. 실행

```bash
python bot.py
```

## 📁 프로젝트 구조

```
cron-estate/
├── bot.py                # 메인 엔트리포인트
├── config.json           # 스캔 설정
├── scraper/
│   ├── naver_land.py     # 네이버부동산 API 클라이언트
│   └── parser.py         # 응답 파싱/가격 포맷팅
├── db/
│   ├── models.py         # DB CRUD
│   └── migrations.py     # 테이블 생성
├── monitor/
│   ├── scheduler.py      # 주기적 스캔 스케줄러
│   ├── diff.py           # 변동 감지 엔진
│   └── grouper.py        # 동/호수 그룹핑
└── discord_bot/
    ├── cog.py            # 슬래시 커맨드
    └── embeds.py         # 디스코드 임베드 포맷
```

## ⚙️ 설정

`config.json`에서 스캔 주기를 변경할 수 있습니다:

```json
{
  "scan_interval_minutes": 30
}
```

## 📝 참고사항

- **첫 스캔 시 알림 없음**: 봇 최초 실행 시에는 DB에 기존 매물을 채우기만 하고 알림을 보내지 않습니다.
- **가격 단위**: 내부적으로 만원 단위로 저장하며, 표시할 때 억/만원으로 변환합니다.
  - 예: `85000` → `8억 5,000만원`
- **Rate Limit**: 네이버부동산 API 호출 시 1.5초 간격으로 요청합니다.

## 📄 라이선스

MIT License
