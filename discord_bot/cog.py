"""
디스코드 슬래시 커맨드 Cog
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from db import models
from discord_bot.embeds import build_listings_embed
from monitor.grouper import group_articles
from scraper.naver_land import NaverLandClient
from scraper.parser import format_price

logger = logging.getLogger("cron-estate.discord")


class HomeCog(commands.Cog):
    """부동산 매물 모니터링 커맨드"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.client = NaverLandClient()

    @app_commands.command(name="매물", description="현재 모니터링 중인 매물 목록을 보여줍니다")
    @app_commands.describe(단지명="특정 단지명 (선택사항)")
    async def show_listings(self, interaction: discord.Interaction, 단지명: str | None = None):
        """현재 매물 목록 (그룹별)"""
        await interaction.response.defer()

        try:
            if 단지명:
                complex_info = await models.find_complex_by_name(단지명)
                if not complex_info:
                    await interaction.followup.send(f"❌ '{단지명}' 단지를 찾을 수 없습니다.")
                    return
                articles = await models.get_active_articles(complex_info["complex_no"])
                name = complex_info["name"]
            else:
                articles = await models.get_active_articles()
                name = "전체"

            if not articles:
                await interaction.followup.send("📭 현재 등록된 매물이 없습니다.")
                return

            # 단지별 그룹핑
            if 단지명:
                groups = group_articles(articles, name)
                embed = build_listings_embed(groups, name)
                await interaction.followup.send(embed=embed)
            else:
                # 단지별로 분리
                by_complex: dict[str, list[dict]] = {}
                for art in articles:
                    cname = art.get("complex_name", "알 수 없음")
                    by_complex.setdefault(cname, []).append(art)

                embeds = []
                for cname, arts in by_complex.items():
                    groups = group_articles(arts, cname)
                    embed = build_listings_embed(groups, cname)
                    embeds.append(embed)

                for embed in embeds[:10]:  # 최대 10개
                    await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"매물 조회 실패: {e}", exc_info=True)
            await interaction.followup.send("❌ 매물 조회 중 오류가 발생했습니다.")

    @app_commands.command(name="단지추가", description="모니터링할 아파트 단지를 추가합니다")
    @app_commands.describe(검색어="단지명 또는 주소로 검색")
    async def add_complex(self, interaction: discord.Interaction, 검색어: str):
        """단지 검색 및 추가"""
        await interaction.response.defer()

        try:
            results = await self.client.search_complex(검색어)
            if not results:
                await interaction.followup.send(f"❌ '{검색어}'에 대한 검색 결과가 없습니다.")
                return

            # 최대 5개까지 표시
            results = results[:5]

            if len(results) == 1:
                # 결과가 1개면 바로 추가
                r = results[0]
                complex_no = str(r.get("complexNo", ""))
                name = r.get("complexName", "")
                address = r.get("address", "") or r.get("roadAddress", "")

                success = await models.add_complex(complex_no, name, address)
                if success:
                    embed = discord.Embed(
                        title="✅ 단지 추가 완료",
                        color=discord.Color.green(),
                    )
                    embed.add_field(name="단지명", value=name, inline=True)
                    embed.add_field(name="단지코드", value=complex_no, inline=True)
                    if address:
                        embed.add_field(name="주소", value=address, inline=False)
                    embed.set_footer(text="다음 스캔부터 매물 모니터링이 시작됩니다.")
                    await interaction.followup.send(embed=embed)

                    # 즉시 초기 스캔
                    if self.bot.scheduler:
                        await self.bot.scheduler.scan_all()
                else:
                    await interaction.followup.send("❌ 단지 추가에 실패했습니다.")
            else:
                # 여러 결과 → 선택지 제시
                embed = discord.Embed(
                    title=f"🔍 '{검색어}' 검색 결과",
                    description="아래 목록에서 추가할 단지를 `/단지추가` 명령으로 정확한 이름을 입력해주세요.",
                    color=discord.Color.blue(),
                )
                for i, r in enumerate(results, 1):
                    name = r.get("complexName", "")
                    addr = r.get("address", "") or r.get("roadAddress", "")
                    code = r.get("complexNo", "")
                    embed.add_field(
                        name=f"{i}. {name}",
                        value=f"📍 {addr}\n🔢 단지코드: {code}",
                        inline=False,
                    )
                await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"단지 추가 실패: {e}", exc_info=True)
            await interaction.followup.send("❌ 단지 검색 중 오류가 발생했습니다.")

    @app_commands.command(name="단지삭제", description="모니터링 단지를 삭제합니다")
    @app_commands.describe(단지명="삭제할 단지명")
    async def remove_complex(self, interaction: discord.Interaction, 단지명: str):
        """단지 모니터링 해제"""
        await interaction.response.defer()

        try:
            complex_info = await models.find_complex_by_name(단지명)
            if not complex_info:
                await interaction.followup.send(f"❌ '{단지명}' 단지를 찾을 수 없습니다.")
                return

            success = await models.remove_complex(complex_info["complex_no"])
            if success:
                await interaction.followup.send(f"✅ **{complex_info['name']}** 모니터링이 해제되었습니다.")
            else:
                await interaction.followup.send("❌ 삭제에 실패했습니다.")

        except Exception as e:
            logger.error(f"단지 삭제 실패: {e}", exc_info=True)
            await interaction.followup.send("❌ 단지 삭제 중 오류가 발생했습니다.")

    @app_commands.command(name="단지목록", description="모니터링 중인 단지 목록을 보여줍니다")
    async def list_complexes(self, interaction: discord.Interaction):
        """모니터링 단지 목록"""
        await interaction.response.defer()

        try:
            complexes = await models.get_active_complexes()
            if not complexes:
                await interaction.followup.send("📭 모니터링 중인 단지가 없습니다.\n`/단지추가` 명령으로 추가해보세요!")
                return

            embed = discord.Embed(
                title="🏘️ 모니터링 단지 목록",
                color=discord.Color.teal(),
            )
            for c in complexes:
                added = c.get("added_at", "")[:10]
                embed.add_field(
                    name=c["name"],
                    value=f"📍 {c.get('address', '-')}\n🔢 {c['complex_no']} | 📅 {added}",
                    inline=False,
                )
            embed.set_footer(text=f"총 {len(complexes)}개 단지")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"단지 목록 조회 실패: {e}", exc_info=True)
            await interaction.followup.send("❌ 목록 조회 중 오류가 발생했습니다.")

    @app_commands.command(name="가격이력", description="특정 호수의 가격 변동 이력을 보여줍니다")
    @app_commands.describe(동="동 이름 (예: 101동)", 호="호수 (예: 1204)")
    async def price_history(self, interaction: discord.Interaction, 동: str, 호: str):
        """가격 변동 이력 조회"""
        await interaction.response.defer()

        try:
            history = await models.get_price_history(dong=동, ho=호)
            if not history:
                await interaction.followup.send(f"📭 {동} {호}호의 가격 변동 이력이 없습니다.")
                return

            embed = discord.Embed(
                title=f"📊 가격 변동 이력: {동} {호}호",
                color=discord.Color.purple(),
            )

            for h in history[:15]:
                old_p = format_price(h["old_price"])
                new_p = format_price(h["new_price"])
                diff = h["new_price"] - h["old_price"]
                direction = "▲" if diff > 0 else "▼"
                changed = h.get("changed_at", "")[:16]
                cname = h.get("complex_name", "")

                embed.add_field(
                    name=f"{changed} [{cname}]",
                    value=f"{old_p} → {new_p} ({direction}{format_price(abs(diff))})",
                    inline=False,
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"가격 이력 조회 실패: {e}", exc_info=True)
            await interaction.followup.send("❌ 가격 이력 조회 중 오류가 발생했습니다.")

    @app_commands.command(name="스캔", description="매물 현황을 즉시 스캔합니다")
    async def scan_now(self, interaction: discord.Interaction):
        """즉시 스캔"""
        await interaction.response.defer()

        try:
            if not self.bot.scheduler:
                await interaction.followup.send("❌ 스케줄러가 초기화되지 않았습니다.")
                return

            await interaction.followup.send("🔄 매물 스캔을 시작합니다...")
            await self.bot.scheduler.scan_now()
            await interaction.followup.send("✅ 스캔 완료!")

        except Exception as e:
            logger.error(f"수동 스캔 실패: {e}", exc_info=True)
            await interaction.followup.send("❌ 스캔 중 오류가 발생했습니다.")
