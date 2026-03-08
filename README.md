# 🏠 Cron-Estate: 네이버부동산 매물 모니터링 CLI

네이버부동산에서 관심 아파트 단지의 매매 매물을 모니터링하는 CLI 도구입니다.
OpenClaw 또는 cron으로 주기적으로 실행하여 매물 변동을 추적합니다.

## ✨ 주요 기능

- 🔍 **매물 스캔**: 네이버부동산 매물 수집 및 변동 감지 (JSON 출력)
- 📊 **브리핑 리포트**: 현황, 추천 매물, 그룹별 매물 정리
- ⭐ **매물 추천**: 가격 하락 / 저가 / 신규 / 장기 매물 자동 추천
- 📋 **중복 그룹핑**: 같은 물건의 여러 중개사 매물을 그룹으로 묶어 표시

## 🚀 설치

```bash
cd cron-estate
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 📋 CLI 명령어

| 명령어 | 설명 |
|--------|------|
| `python cli.py scan` | 모든 모니터링 단지 매물 스캔 (JSON 출력) |
| `python cli.py report` | 매물 브리핑 리포트 (텍스트 출력) |
| `python cli.py add <검색어>` | 단지 검색 후 모니터링 추가 |
| `python cli.py remove <단지명>` | 모니터링 단지 제거 |
| `python cli.py list` | 모니터링 중인 단지 목록 |
| `python cli.py status` | DB 통계 (매물 수, 마지막 스캔 등) |

### 사용 예시

```bash
# 단지 추가
python cli.py add 매탄위브하늘채

# 매물 스캔 (JSON 출력)
python cli.py scan

# 브리핑 리포트
python cli.py report

# 상태 확인
python cli.py status
```

### scan 출력 예시

```json
{
  "complex_name": "매탄위브하늘채",
  "scanned_at": "2026-03-08T09:00:00",
  "total_articles": 12,
  "new": [{"dong": "102", "ho": "801", "area": 84, "price": 88000}],
  "price_changes": [{"dong": "101", "ho": "502", "old_price": 90000, "new_price": 87000}],
  "removed": []
}
```

### report 출력 예시

```
=== 매물 브리핑 ===
📅 2026-03-08 09:00

📊 현황: 매탄위브하늘채
  총 매물: 12건 (활성)
  신규: 2건 (24시간 내)
  가격변동: 1건
  삭제: 0건

⭐ 추천 매물
  1. [가격하락] 101동 502호 | 84㎡ | 8억 7,000만원 (▼3,000만원)
  2. [저가매물] 103동 1204호 | 84㎡ | 8억 5,000만원 (평균 대비 -5,000만원)
  3. [신규] 102동 801호 | 84㎡ | 8억 8,000만원

📋 전체 매물 (그룹별)
  [103동 1204호] | 84㎡ | 8억 5,000만원 ~ 8억 7,000만원 (3건)
  [101동 502호] | 84㎡ | 8억 7,000만원
```

## ⏰ 자동 실행 (OpenClaw / cron)

이 도구는 자체 스케줄러 없이, 외부에서 주기적으로 호출하는 방식으로 동작합니다.

### OpenClaw cron 예시

```bash
# 30분마다 스캔
openclaw cron add --schedule "*/30 * * * *" --command "cd ~/cron-estate && python cli.py scan"

# 아침/오후 리포트
openclaw cron add --schedule "0 9,14 * * *" --command "cd ~/cron-estate && python cli.py report"
```

### 시스템 cron 예시

```bash
# crontab -e
*/30 * * * * cd /path/to/cron-estate && /path/to/venv/bin/python cli.py scan
0 9,14 * * * cd /path/to/cron-estate && /path/to/venv/bin/python cli.py report
```

## 📁 프로젝트 구조

```
cron-estate/
├── cli.py                # CLI 엔트리포인트
├── config.json           # 설정
├── scraper/
│   ├── naver_land.py     # 네이버부동산 API 클라이언트
│   └── parser.py         # 응답 파싱/가격 포맷팅
├── db/
│   ├── models.py         # DB CRUD + 통계/추천 쿼리
│   └── migrations.py     # 테이블 생성
└── monitor/
    ├── diff.py           # 변동 감지 엔진
    ├── grouper.py        # 동/호수 그룹핑
    └── recommender.py    # 매물 추천 엔진
```

## 📝 참고

- **첫 스캔**: 초기 스캔 시에는 모든 매물을 DB에 등록만 하고 변동으로 표시하지 않습니다.
- **가격 단위**: 내부적으로 만원 단위로 저장 (예: `85000` → `8억 5,000만원`)
- **Rate Limit**: 네이버부동산 API 호출 간 1.5초 딜레이 적용
- **Discord 불필요**: 별도의 Discord 토큰이나 봇 설정 없이 독립 실행

## 📄 라이선스

MIT License
