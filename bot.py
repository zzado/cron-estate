"""
cron-estate: 네이버부동산 매물 모니터링 디스코드 봇
메인 엔트리포인트
"""

import asyncio
import logging
import os
import sys

import discord
from discord.ext import commands
from dotenv import load_dotenv

from db.migrations import initialize_database
from discord_bot.cog import HomeCog
from monitor.scheduler import MonitorScheduler

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("cron-estate")

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

if not DISCORD_TOKEN:
    logger.error("DISCORD_TOKEN이 설정되지 않았습니다. .env 파일을 확인하세요.")
    sys.exit(1)

if not CHANNEL_ID:
    logger.error("CHANNEL_ID가 설정되지 않았습니다. .env 파일을 확인하세요.")
    sys.exit(1)


class CronEstateBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.channel_id = int(CHANNEL_ID)
        self.scheduler: MonitorScheduler | None = None

    async def setup_hook(self):
        """봇 시작 시 초기화"""
        # DB 초기화
        await initialize_database()
        logger.info("데이터베이스 초기화 완료")

        # Cog 등록
        cog = HomeCog(self)
        await self.add_cog(cog)
        logger.info("HomeCog 등록 완료")

        # 슬래시 커맨드 동기화
        await self.tree.sync()
        logger.info("슬래시 커맨드 동기화 완료")

        # 스케줄러 시작
        self.scheduler = MonitorScheduler(self)
        self.scheduler.start()
        logger.info("모니터링 스케줄러 시작")

    async def on_ready(self):
        logger.info(f"봇 로그인 완료: {self.user} (ID: {self.user.id})")
        logger.info(f"알림 채널: {self.channel_id}")


async def main():
    bot = CronEstateBot()
    async with bot:
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
