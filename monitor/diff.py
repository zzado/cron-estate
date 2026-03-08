from __future__ import annotations

"""
매물 변동 감지 엔진
신규 매물, 가격 변동, 삭제된 매물을 탐지
"""

import logging
from dataclasses import dataclass

from db import models
from scraper.parser import ArticleInfo

logger = logging.getLogger("cron-estate.monitor.diff")


@dataclass
class ScanResult:
    """스캔 결과"""

    complex_no: str
    complex_name: str
    new_articles: list[ArticleInfo]
    price_changes: list[dict]  # {"article": ArticleInfo, "old_price": int, "new_price": int}
    removed_articles: list[dict]
    total_active: int


async def process_scan(
    complex_no: str,
    complex_name: str,
    articles: list[ArticleInfo],
) -> ScanResult:
    """스캔 결과를 DB와 비교하여 변동 사항 감지"""
    new_articles = []
    price_changes = []

    # 현재 스캔에서 발견된 매물 번호
    active_article_nos = {a.article_no for a in articles}

    # 초기 스캔 여부 확인
    is_first_scan = not await models.has_any_articles()

    for article in articles:
        result = await models.upsert_article(
            article_no=article.article_no,
            complex_no=article.complex_no,
            article_name=article.article_name,
            dong=article.dong,
            ho=article.ho,
            exclusive_area=article.exclusive_area,
            supply_area=article.supply_area,
            deal_price=article.deal_price,
            floor=article.floor,
            direction=article.direction,
            realtor_name=article.realtor_name,
            article_url=article.article_url,
            group_key=article.group_key,
        )

        if result and not is_first_scan:
            if result["type"] == "new":
                new_articles.append(article)
            elif result["type"] == "price_change":
                price_changes.append({
                    "article": article,
                    "old_price": result["old_price"],
                    "new_price": result["new_price"],
                })

    # 삭제된 매물 감지
    removed = []
    if not is_first_scan:
        removed = await models.mark_removed_articles(complex_no, active_article_nos)

    if is_first_scan:
        logger.info(f"[{complex_name}] 초기 스캔 완료: {len(articles)}건 등록 (알림 없음)")
    else:
        logger.info(
            f"[{complex_name}] 스캔 완료: "
            f"신규 {len(new_articles)}건, "
            f"가격변동 {len(price_changes)}건, "
            f"삭제 {len(removed)}건"
        )

    return ScanResult(
        complex_no=complex_no,
        complex_name=complex_name,
        new_articles=new_articles,
        price_changes=price_changes,
        removed_articles=removed,
        total_active=len(articles),
    )
