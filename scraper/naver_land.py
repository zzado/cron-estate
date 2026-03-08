from __future__ import annotations

"""
네이버부동산 API 클라이언트
"""

import asyncio
import logging
from typing import Any

import aiohttp

logger = logging.getLogger("cron-estate.scraper")

BASE_URL = "https://new.land.naver.com/api"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://new.land.naver.com/",
    "Accept": "application/json",
}

# 요청 간 딜레이 (초)
REQUEST_DELAY = 1.5


class NaverLandClient:
    """네이버부동산 API 비동기 클라이언트"""

    def __init__(self):
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=HEADERS)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(self, url: str, params: dict | None = None) -> dict | list | None:
        """API 요청 (rate limit 포함)"""
        session = await self._get_session()
        try:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json(content_type=None)
                else:
                    text = await resp.text()
                    logger.warning(f"API 요청 실패: {resp.status} - {url} - {text[:200]}")
                    return None
        except Exception as e:
            logger.error(f"API 요청 에러: {url} - {e}")
            return None
        finally:
            await asyncio.sleep(REQUEST_DELAY)

    async def search_complex(self, query: str) -> list[dict[str, Any]]:
        """단지 검색

        Returns:
            list of {"complexNo": str, "complexName": str, "address": str, ...}
        """
        url = f"{BASE_URL}/search"
        data = await self._request(url, params={"query": query})
        if data and isinstance(data, dict):
            return data.get("complexes", [])
        return []

    async def get_articles(self, complex_no: str) -> list[dict[str, Any]]:
        """단지의 매매 매물 목록 (페이지네이션 포함)"""
        all_articles = []
        page = 1

        while True:
            url = f"{BASE_URL}/articles/complex/{complex_no}"
            params = {
                "realEstateType": "APT",
                "tradeType": "A1",
                "sameAddressGroup": "true",
                "page": str(page),
                "order": "rank",
            }
            data = await self._request(url, params=params)
            if not data or not isinstance(data, dict):
                break

            articles = data.get("articleList", [])
            if not articles:
                break

            all_articles.extend(articles)

            # 더 이상 페이지가 없으면 중단
            total = data.get("isMoreData", False)
            if not total:
                break

            page += 1

        logger.info(f"단지 {complex_no}: 매물 {len(all_articles)}건 조회")
        return all_articles

    async def get_article_detail(self, article_no: str) -> dict[str, Any] | None:
        """매물 상세 정보 조회"""
        url = f"{BASE_URL}/articles/{article_no}"
        data = await self._request(url)
        if data and isinstance(data, dict):
            return data.get("articleDetail", data)
        return None
