"""
디스코드 알림 임베드 포맷
"""

from datetime import datetime

import discord

from scraper.parser import ArticleInfo, format_price


def build_new_listing_embed(article: ArticleInfo, complex_name: str) -> discord.Embed:
    """새 매물 알림 임베드"""
    embed = discord.Embed(
        title=f"🏠 [{complex_name}] 새 매물 발견!",
        color=discord.Color.blue(),
        timestamp=datetime.now(),
    )

    # 위치
    location_parts = []
    if article.dong:
        location_parts.append(article.dong)
    if article.ho:
        location_parts.append(f"{article.ho}호")
    location = " ".join(location_parts) if location_parts else "동/호수 미상"

    area_str = f"전용 {article.exclusive_area:.0f}㎡" if article.exclusive_area else ""
    floor_str = f"{article.floor}" if article.floor else ""

    info_parts = [p for p in [location, area_str, floor_str] if p]
    embed.add_field(name="📍 위치", value=" | ".join(info_parts) if info_parts else "-", inline=False)

    # 가격
    embed.add_field(name="💰 매매가", value=format_price(article.deal_price), inline=True)

    # 향
    if article.direction:
        embed.add_field(name="🧭 향", value=article.direction, inline=True)

    # 중개사
    if article.realtor_name:
        embed.add_field(name="🏢 중개사", value=article.realtor_name, inline=True)

    # 링크
    if article.article_url:
        embed.add_field(name="🔗 링크", value=f"[네이버부동산]({article.article_url})", inline=False)

    return embed


def build_price_change_embed(
    article: ArticleInfo,
    complex_name: str,
    old_price: int,
    new_price: int,
) -> discord.Embed:
    """가격 변동 알림 임베드"""
    diff = new_price - old_price
    pct = (diff / old_price * 100) if old_price > 0 else 0

    if diff > 0:
        direction = "▲"
        color = discord.Color.red()
    else:
        direction = "▼"
        color = discord.Color.green()

    embed = discord.Embed(
        title=f"📊 [{complex_name}] 가격 변동!",
        color=color,
        timestamp=datetime.now(),
    )

    # 위치
    location_parts = []
    if article.dong:
        location_parts.append(article.dong)
    if article.ho:
        location_parts.append(f"{article.ho}호")
    location = " ".join(location_parts) if location_parts else "동/호수 미상"

    area_str = f"전용 {article.exclusive_area:.0f}㎡" if article.exclusive_area else ""
    info_parts = [p for p in [location, area_str] if p]
    embed.add_field(name="📍 위치", value=" | ".join(info_parts) if info_parts else "-", inline=False)

    # 가격 변동
    price_str = (
        f"{format_price(old_price)} → {format_price(new_price)}\n"
        f"({direction}{format_price(abs(diff))}, {pct:+.1f}%)"
    )
    embed.add_field(name="💰 가격", value=price_str, inline=False)

    if article.article_url:
        embed.add_field(name="🔗 링크", value=f"[네이버부동산]({article.article_url})", inline=False)

    return embed


def build_removed_embed(article_data: dict, complex_name: str) -> discord.Embed:
    """매물 삭제 알림 임베드"""
    embed = discord.Embed(
        title=f"✅ [{complex_name}] 매물 삭제됨 (거래완료 추정)",
        color=discord.Color.gold(),
        timestamp=datetime.now(),
    )

    # 위치
    dong = article_data.get("dong", "")
    ho = article_data.get("ho", "")
    location_parts = []
    if dong:
        location_parts.append(dong)
    if ho:
        location_parts.append(f"{ho}호")
    location = " ".join(location_parts) if location_parts else "동/호수 미상"

    area = article_data.get("exclusive_area", 0)
    area_str = f"전용 {area:.0f}㎡" if area else ""
    info_parts = [p for p in [location, area_str] if p]
    embed.add_field(name="📍 위치", value=" | ".join(info_parts) if info_parts else "-", inline=False)

    # 마지막 가격
    price = article_data.get("deal_price", 0)
    embed.add_field(name="💰 마지막 가격", value=format_price(price), inline=True)

    # 등록 기간
    first_seen = article_data.get("first_seen_at", "")
    if first_seen:
        try:
            first_dt = datetime.strptime(first_seen, "%Y-%m-%d %H:%M:%S")
            days = (datetime.now() - first_dt).days
            embed.add_field(name="📅 등록 기간", value=f"{days}일", inline=True)
        except ValueError:
            pass

    return embed


def build_listings_embed(
    groups: list,
    complex_name: str,
    page: int = 1,
    total_pages: int = 1,
) -> discord.Embed:
    """매물 목록 임베드"""
    embed = discord.Embed(
        title=f"🏘️ [{complex_name}] 현재 매물 현황",
        color=discord.Color.teal(),
        timestamp=datetime.now(),
    )

    if not groups:
        embed.description = "현재 등록된 매물이 없습니다."
        return embed

    for group in groups:
        location = group.location_display
        area_str = f"전용 {group.exclusive_area:.0f}㎡" if group.exclusive_area else ""

        value_parts = []
        value_parts.append(f"💰 {group.price_display}")
        if group.count > 1:
            value_parts.append(f"📋 매물 {group.count}건")
        if area_str:
            value_parts.append(area_str)

        # 각 매물의 층/중개사
        for art in group.articles[:3]:  # 최대 3개까지만
            floor = art.get("floor", "")
            realtor = art.get("realtor_name", "")
            price = format_price(art.get("deal_price", 0))
            detail_parts = [p for p in [price, floor, realtor] if p]
            if detail_parts:
                value_parts.append(f"  └ {' | '.join(detail_parts)}")

        if group.count > 3:
            value_parts.append(f"  └ ...외 {group.count - 3}건")

        embed.add_field(
            name=f"📍 {location}",
            value="\n".join(value_parts),
            inline=False,
        )

    if total_pages > 1:
        embed.set_footer(text=f"페이지 {page}/{total_pages}")

    return embed
