from __future__ import annotations

"""
매물 추천 엔진
가격 하락, 신규, 저가, 장기 매물을 분석하여 추천
"""

import logging
from datetime import datetime, timedelta

from db import models

logger = logging.getLogger("cron-estate.recommender")


async def get_recommendations(complex_no: str | None = None) -> list[dict]:
    """추천 매물 목록 반환

    추천 기준:
    1. 가격 하락 매물 (priority 100)
    2. 신규 매물 - 24시간 이내 (priority 80)
    3. 평균 대비 저가 매물 (priority 60)
    4. 장기 매물 - 14일 이상 (priority 40)

    Returns:
        list[dict]: 각 항목은 article data + reason + priority
    """
    recommendations = []

    # 1. 가격 하락 매물
    price_drops = await _get_price_drop_recommendations(complex_no)
    recommendations.extend(price_drops)

    # 2. 신규 매물
    new_listings = await _get_new_listing_recommendations(complex_no)
    recommendations.extend(new_listings)

    # 3. 평균 대비 저가 매물
    below_avg = await _get_below_average_recommendations(complex_no)
    recommendations.extend(below_avg)

    # 4. 장기 매물
    long_listed = await _get_long_listed_recommendations(complex_no)
    recommendations.extend(long_listed)

    # 중복 제거 (같은 article_no가 여러 이유로 추천될 수 있음 → 가장 높은 priority만)
    seen = {}
    for rec in recommendations:
        ano = rec["article_no"]
        if ano not in seen or rec["priority"] > seen[ano]["priority"]:
            seen[ano] = rec

    result = sorted(seen.values(), key=lambda x: x["priority"], reverse=True)
    return result


async def _get_price_drop_recommendations(complex_no: str | None) -> list[dict]:
    """최근 가격 하락 매물"""
    recs = []
    articles = await models.get_active_articles(complex_no)

    for article in articles:
        history = await models.get_price_history(
            dong=article.get("dong", ""),
            ho=article.get("ho", ""),
            complex_no=article.get("complex_no"),
        )
        if not history:
            continue

        # 최근 가격 변동 중 하락인 것
        latest = history[0]
        if latest["new_price"] < latest["old_price"]:
            diff = latest["old_price"] - latest["new_price"]
            from scraper.parser import format_price
            recs.append({
                **article,
                "reason": f"가격하락",
                "reason_detail": f"▼{format_price(diff)}",
                "priority": 100,
                "price_diff": -diff,
            })

    return recs


async def _get_new_listing_recommendations(complex_no: str | None) -> list[dict]:
    """24시간 이내 신규 매물"""
    recs = []
    changes = await models.get_recent_changes(hours=24)

    for change in changes.get("new", []):
        if complex_no and change.get("complex_no") != complex_no:
            continue
        recs.append({
            **change,
            "reason": "신규",
            "reason_detail": "24시간 이내 등록",
            "priority": 80,
        })

    return recs


async def _get_below_average_recommendations(complex_no: str | None) -> list[dict]:
    """평균 대비 저가 매물"""
    recs = []
    articles = await models.get_active_articles(complex_no)

    # 단지별로 평균가 계산
    complexes_to_check = set()
    for a in articles:
        complexes_to_check.add(a.get("complex_no", ""))

    avg_by_area = {}
    for cno in complexes_to_check:
        if cno:
            avg_data = await models.get_average_price_by_area(cno)
            avg_by_area[cno] = avg_data

    for article in articles:
        cno = article.get("complex_no", "")
        area = article.get("exclusive_area", 0)
        price = article.get("deal_price", 0)

        if not cno or not area or not price:
            continue

        area_key = f"{area:.0f}"
        avg_info = avg_by_area.get(cno, {}).get(area_key)
        if not avg_info:
            continue

        avg_price = avg_info["avg_price"]
        if avg_info["count"] < 2:
            continue  # 비교 대상이 너무 적음

        diff = price - avg_price
        if diff < 0 and abs(diff) >= avg_price * 0.03:  # 3% 이상 저가
            from scraper.parser import format_price
            recs.append({
                **article,
                "reason": "저가매물",
                "reason_detail": f"평균 대비 -{format_price(abs(int(diff)))}",
                "priority": 60,
                "price_diff_from_avg": diff,
            })

    return recs


async def _get_long_listed_recommendations(complex_no: str | None) -> list[dict]:
    """14일 이상 장기 매물"""
    recs = []
    articles = await models.get_active_articles(complex_no)

    now = datetime.now()
    threshold = now - timedelta(days=14)

    for article in articles:
        first_seen = article.get("first_seen_at", "")
        if not first_seen:
            continue
        try:
            first_dt = datetime.strptime(first_seen, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

        if first_dt <= threshold:
            days = (now - first_dt).days
            recs.append({
                **article,
                "reason": "장기매물",
                "reason_detail": f"{days}일째 등록 (협상 가능성)",
                "priority": 40,
                "days_listed": days,
            })

    return recs
