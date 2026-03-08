"""
APScheduler 기반 주기적 스캔 스케줄러
"""

import json
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from db import models
from monitor.diff import process_scan
from scraper.naver_land import NaverLandClient
from scraper.parser import parse_article

logger = logging.getLogger("cron-estate.scheduler")

CONFIG_PATH = "config.json"


def load_config() -> dict:
    """설정 파일 로드"""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"설정 파일 없음: {CONFIG_PATH}")
        return {"scan_interval_minutes": 30, "complexes": []}


class MonitorScheduler:
    """매물 모니터링 스케줄러"""

    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self.client = NaverLandClient()
        config = load_config()
        self.interval = config.get("scan_interval_minutes", 30)

    def start(self):
        """스케줄러 시작"""
        self.scheduler.add_job(
            self.scan_all,
            "interval",
            minutes=self.interval,
            id="scan_all",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info(f"스케줄러 시작: {self.interval}분 간격")

    def stop(self):
        """스케줄러 중지"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        logger.info("스케줄러 중지")

    async def scan_all(self):
        """모든 모니터링 단지 스캔"""
        from discord_bot.embeds import (
            build_new_listing_embed,
            build_price_change_embed,
            build_removed_embed,
        )

        complexes = await models.get_active_complexes()
        if not complexes:
            logger.info("모니터링 대상 단지 없음")
            return

        channel = self.bot.get_channel(self.bot.channel_id)
        if not channel:
            logger.warning(f"채널을 찾을 수 없음: {self.bot.channel_id}")
            return

        for complex_info in complexes:
            try:
                await self._scan_complex(complex_info, channel)
            except Exception as e:
                logger.error(f"단지 스캔 실패 [{complex_info['name']}]: {e}", exc_info=True)

    async def _scan_complex(self, complex_info: dict, channel):
        """단일 단지 스캔"""
        from discord_bot.embeds import (
            build_new_listing_embed,
            build_price_change_embed,
            build_removed_embed,
        )

        complex_no = complex_info["complex_no"]
        complex_name = complex_info["name"]

        logger.info(f"스캔 시작: {complex_name} ({complex_no})")

        # API에서 매물 가져오기
        raw_articles = await self.client.get_articles(complex_no)
        articles = [parse_article(raw, complex_no) for raw in raw_articles]

        # 변동 감지
        result = await process_scan(complex_no, complex_name, articles)

        # 알림 전송
        for article in result.new_articles:
            embed = build_new_listing_embed(article, complex_name)
            await channel.send(embed=embed)

        for change in result.price_changes:
            embed = build_price_change_embed(
                change["article"],
                complex_name,
                change["old_price"],
                change["new_price"],
            )
            await channel.send(embed=embed)

        for removed in result.removed_articles:
            embed = build_removed_embed(removed, complex_name)
            await channel.send(embed=embed)

    async def scan_now(self):
        """즉시 스캔 (수동 트리거)"""
        await self.scan_all()
