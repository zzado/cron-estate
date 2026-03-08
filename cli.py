#!/usr/bin/env python3
"""
cron-estate CLI: 네이버부동산 매물 모니터링 도구
"""

import asyncio
import json
import logging
import sys
from datetime import datetime

import click

from db.migrations import initialize_database
from db import models
from monitor.diff import process_scan
from monitor.grouper import group_articles
from monitor.recommender import get_recommendations
from scraper.naver_land import NaverLandClient
from scraper.parser import parse_article, format_price

# 로깅 설정
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("cron-estate")


def run_async(coro):
    """비동기 함수를 동기적으로 실행"""
    return asyncio.run(coro)


async def _ensure_db():
    """DB 초기화 보장"""
    await initialize_database()


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="상세 로그 출력")
def cli(verbose):
    """🏠 cron-estate: 네이버부동산 매물 모니터링 CLI"""
    if verbose:
        logging.getLogger("cron-estate").setLevel(logging.DEBUG)


@cli.command()
def scan():
    """모니터링 중인 모든 단지의 매물을 스캔합니다."""
    run_async(_scan())


async def _scan():
    await _ensure_db()

    complexes = await models.get_active_complexes()
    if not complexes:
        click.echo(json.dumps({"error": "모니터링 중인 단지가 없습니다."}, ensure_ascii=False))
        return

    client = NaverLandClient()
    results = []

    try:
        for complex_info in complexes:
            complex_no = complex_info["complex_no"]
            complex_name = complex_info["name"]

            try:
                raw_articles = await client.get_articles(complex_no)
                articles = [parse_article(raw, complex_no) for raw in raw_articles]
                scan_result = await process_scan(complex_no, complex_name, articles)

                result = {
                    "complex_name": complex_name,
                    "complex_no": complex_no,
                    "scanned_at": datetime.now().isoformat(timespec="seconds"),
                    "total_articles": scan_result.total_active,
                    "new": [
                        {
                            "dong": a.dong,
                            "ho": a.ho,
                            "area": a.exclusive_area,
                            "price": a.deal_price,
                        }
                        for a in scan_result.new_articles
                    ],
                    "price_changes": [
                        {
                            "dong": c["article"].dong,
                            "ho": c["article"].ho,
                            "old_price": c["old_price"],
                            "new_price": c["new_price"],
                        }
                        for c in scan_result.price_changes
                    ],
                    "removed": [
                        {
                            "dong": r.get("dong", ""),
                            "ho": r.get("ho", ""),
                            "price": r.get("deal_price", 0),
                        }
                        for r in scan_result.removed_articles
                    ],
                }
                results.append(result)

            except Exception as e:
                logger.error(f"단지 스캔 실패 [{complex_name}]: {e}")
                results.append({
                    "complex_name": complex_name,
                    "complex_no": complex_no,
                    "error": str(e),
                })
    finally:
        await client.close()

    # 단일 단지면 객체로, 복수면 배열로 출력
    if len(results) == 1:
        click.echo(json.dumps(results[0], ensure_ascii=False, indent=2))
    else:
        click.echo(json.dumps(results, ensure_ascii=False, indent=2))


@cli.command()
def report():
    """현재 매물 브리핑 리포트를 생성합니다."""
    run_async(_report())


async def _report():
    await _ensure_db()

    complexes = await models.get_active_complexes()
    if not complexes:
        click.echo("모니터링 중인 단지가 없습니다.")
        return

    now = datetime.now()
    click.echo(f"=== 매물 브리핑 ===")
    click.echo(f"📅 {now.strftime('%Y-%m-%d %H:%M')}")
    click.echo()

    changes = await models.get_recent_changes(hours=24)

    for complex_info in complexes:
        complex_no = complex_info["complex_no"]
        complex_name = complex_info["name"]

        articles = await models.get_active_articles(complex_no)

        # 해당 단지의 변동 사항 필터
        new_count = len([c for c in changes["new"] if c.get("complex_no") == complex_no])
        price_change_count = len([c for c in changes["price_changes"] if c.get("complex_no") == complex_no])
        removed_count = len([c for c in changes["removed"] if c.get("complex_no") == complex_no])

        click.echo(f"📊 현황: {complex_name}")
        click.echo(f"  총 매물: {len(articles)}건 (활성)")
        click.echo(f"  신규: {new_count}건 (24시간 내)")
        click.echo(f"  가격변동: {price_change_count}건")
        click.echo(f"  삭제: {removed_count}건")
        click.echo()

        # 추천 매물
        recs = await get_recommendations(complex_no)
        if recs:
            click.echo(f"⭐ 추천 매물")
            for i, rec in enumerate(recs[:5], 1):
                dong = rec.get("dong", "")
                ho = rec.get("ho", "")
                area = rec.get("exclusive_area", 0)
                price = rec.get("deal_price", 0)
                reason = rec.get("reason", "")
                detail = rec.get("reason_detail", "")

                location = f"{dong} {ho}호" if dong and ho else dong or ho or "미상"
                area_str = f"{area:.0f}㎡" if area else ""

                line = f"  {i}. [{reason}] {location}"
                if area_str:
                    line += f" | {area_str}"
                line += f" | {format_price(price)}"
                if detail:
                    line += f" ({detail})"
                click.echo(line)
            click.echo()

        # 전체 매물 (그룹별)
        if articles:
            groups = group_articles(articles, complex_name)
            click.echo(f"📋 전체 매물 (그룹별)")
            for group in groups:
                location = group.location_display
                area_str = f"{group.exclusive_area:.0f}㎡" if group.exclusive_area else ""
                count_str = f"({group.count}건)" if group.count > 1 else ""

                parts = [f"  [{location}]"]
                if area_str:
                    parts.append(area_str)
                parts.append(group.price_display)
                if count_str:
                    parts.append(count_str)

                click.echo(" | ".join(parts))
            click.echo()

    # 리포트 전송 시간 기록
    await models.mark_report_sent()


@cli.command("add")
@click.argument("query")
def add_complex(query):
    """단지를 검색하여 모니터링에 추가합니다."""
    run_async(_add_complex(query))


async def _add_complex(query: str):
    await _ensure_db()

    client = NaverLandClient()
    try:
        results = await client.search_complex(query)
    finally:
        await client.close()

    if not results:
        click.echo(f"❌ '{query}'에 대한 검색 결과가 없습니다.")
        return

    results = results[:5]

    if len(results) == 1:
        r = results[0]
        complex_no = str(r.get("complexNo", ""))
        name = r.get("complexName", "")
        address = r.get("address", "") or r.get("roadAddress", "")

        success = await models.add_complex(complex_no, name, address)
        if success:
            click.echo(f"✅ 단지 추가 완료")
            click.echo(f"  단지명: {name}")
            click.echo(f"  단지코드: {complex_no}")
            if address:
                click.echo(f"  주소: {address}")
            click.echo(f"  다음 스캔부터 매물 모니터링이 시작됩니다.")
        else:
            click.echo("❌ 단지 추가에 실패했습니다.")
    else:
        click.echo(f"🔍 '{query}' 검색 결과:")
        click.echo()
        for i, r in enumerate(results, 1):
            name = r.get("complexName", "")
            addr = r.get("address", "") or r.get("roadAddress", "")
            code = r.get("complexNo", "")
            click.echo(f"  {i}. {name}")
            click.echo(f"     📍 {addr}")
            click.echo(f"     🔢 단지코드: {code}")
            click.echo()

        # 선택
        choice = click.prompt("추가할 단지 번호를 선택하세요 (취소: 0)", type=int, default=0)
        if choice < 1 or choice > len(results):
            click.echo("취소되었습니다.")
            return

        r = results[choice - 1]
        complex_no = str(r.get("complexNo", ""))
        name = r.get("complexName", "")
        address = r.get("address", "") or r.get("roadAddress", "")

        success = await models.add_complex(complex_no, name, address)
        if success:
            click.echo(f"✅ {name} 추가 완료!")
        else:
            click.echo("❌ 단지 추가에 실패했습니다.")


@cli.command("remove")
@click.argument("name")
def remove_complex(name):
    """단지를 모니터링에서 제거합니다."""
    run_async(_remove_complex(name))


async def _remove_complex(name: str):
    await _ensure_db()

    complex_info = await models.find_complex_by_name(name)
    if not complex_info:
        click.echo(f"❌ '{name}' 단지를 찾을 수 없습니다.")
        return

    success = await models.remove_complex(complex_info["complex_no"])
    if success:
        click.echo(f"✅ {complex_info['name']} 모니터링이 해제되었습니다.")
    else:
        click.echo("❌ 삭제에 실패했습니다.")


@cli.command("list")
def list_complexes():
    """모니터링 중인 단지 목록을 보여줍니다."""
    run_async(_list_complexes())


async def _list_complexes():
    await _ensure_db()

    complexes = await models.get_active_complexes()
    if not complexes:
        click.echo("📭 모니터링 중인 단지가 없습니다.")
        click.echo("   'python cli.py add <단지명>'으로 추가해보세요!")
        return

    click.echo(f"🏘️ 모니터링 단지 목록 ({len(complexes)}개)")
    click.echo()
    for c in complexes:
        added = c.get("added_at", "")[:10]
        click.echo(f"  • {c['name']}")
        click.echo(f"    📍 {c.get('address', '-')}")
        click.echo(f"    🔢 {c['complex_no']} | 📅 {added}")
        click.echo()


@cli.command()
def status():
    """DB 통계 정보를 보여줍니다."""
    run_async(_status())


async def _status():
    await _ensure_db()

    stats = await models.get_stats()

    click.echo("📊 cron-estate 상태")
    click.echo()
    click.echo(f"  모니터링 단지: {stats['complexes']}개")
    click.echo(f"  전체 매물: {stats['total_articles']}건")
    click.echo(f"  활성 매물: {stats['active_articles']}건")
    click.echo(f"  가격 변동 기록: {stats['price_changes']}건")
    click.echo(f"  마지막 스캔: {stats['last_scan'] or '없음'}")
    click.echo(f"  마지막 리포트: {stats['last_report'] or '없음'}")


if __name__ == "__main__":
    cli()
