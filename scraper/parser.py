"""
네이버부동산 API 응답 파싱/정규화
"""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("cron-estate.parser")


@dataclass
class ArticleInfo:
    """파싱된 매물 정보"""

    article_no: str
    complex_no: str
    article_name: str = ""
    dong: str = ""
    ho: str = ""
    exclusive_area: float = 0.0
    supply_area: float = 0.0
    deal_price: int = 0  # 만원 단위
    floor: str = ""
    direction: str = ""
    realtor_name: str = ""
    article_url: str = ""
    group_key: str = ""

    def __post_init__(self):
        if not self.group_key:
            self.group_key = make_group_key(
                self.complex_no, self.dong, self.ho, self.exclusive_area
            )


def make_group_key(complex_no: str, dong: str, ho: str, exclusive_area: float) -> str:
    """그룹핑 키 생성"""
    area_str = f"{exclusive_area:.1f}" if exclusive_area else "0"
    return f"{complex_no}_{dong}_{ho}_{area_str}"


def parse_article(raw: dict[str, Any], complex_no: str) -> ArticleInfo:
    """API 응답의 매물 데이터를 ArticleInfo로 변환"""
    article_no = str(raw.get("articleNo", ""))

    # 동/호수 파싱
    dong = raw.get("buildingName", "") or ""  # buildingName이 동 이름
    ho = raw.get("hoNo", "") or ""

    # 면적 파싱
    exclusive_area = _parse_float(raw.get("exclusiveArea", 0))
    supply_area = _parse_float(raw.get("supplyArea", 0) or raw.get("areaSize", 0))

    # 가격 파싱 (만원 단위)
    deal_price = _parse_price(raw.get("dealOrWarrantPrc", ""))

    # 층
    floor_info = raw.get("floorInfo", "") or ""

    # 향
    direction = raw.get("direction", "") or ""

    # 중개사
    realtor_name = raw.get("realtorName", "") or ""

    # 매물명
    article_name = raw.get("articleName", "") or ""

    # URL
    article_url = f"https://new.land.naver.com/articles/{article_no}" if article_no else ""

    return ArticleInfo(
        article_no=article_no,
        complex_no=complex_no,
        article_name=article_name,
        dong=dong,
        ho=ho,
        exclusive_area=exclusive_area,
        supply_area=supply_area,
        deal_price=deal_price,
        floor=floor_info,
        direction=direction,
        realtor_name=realtor_name,
        article_url=article_url,
    )


def _parse_float(value: Any) -> float:
    """숫자로 변환"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _parse_price(price_str: str) -> int:
    """가격 문자열을 만원 단위 정수로 변환

    예: "8억 5,000" → 85000
        "12억" → 120000
        "5,000" → 5000
    """
    if not price_str:
        return 0

    price_str = str(price_str).strip().replace(",", "")
    total = 0

    if "억" in price_str:
        parts = price_str.split("억")
        try:
            eok = int(parts[0].strip())
            total += eok * 10000
        except ValueError:
            pass

        if len(parts) > 1 and parts[1].strip():
            try:
                remainder = int(parts[1].strip())
                total += remainder
            except ValueError:
                pass
    else:
        try:
            total = int(price_str)
        except ValueError:
            pass

    return total


def format_price(price_man: int) -> str:
    """만원 단위 가격을 한국어 형식으로 변환

    예: 85000 → "8억 5,000만원"
        120000 → "12억"
        5000 → "5,000만원"
    """
    if price_man <= 0:
        return "가격 미정"

    eok = price_man // 10000
    remainder = price_man % 10000

    if eok > 0 and remainder > 0:
        return f"{eok}억 {remainder:,}만원"
    elif eok > 0:
        return f"{eok}억"
    else:
        return f"{remainder:,}만원"
