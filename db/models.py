"""
데이터베이스 CRUD 모델
"""

import logging
from datetime import datetime

import aiosqlite

from db.migrations import DB_PATH

logger = logging.getLogger("cron-estate.db")


async def get_db() -> aiosqlite.Connection:
    """DB 연결 생성"""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


# ==================== Complexes ====================


async def add_complex(complex_no: str, name: str, address: str = "") -> bool:
    """모니터링 단지 추가"""
    async with await get_db() as db:
        try:
            await db.execute(
                "INSERT OR REPLACE INTO complexes (complex_no, name, address, active) VALUES (?, ?, ?, 1)",
                (complex_no, name, address),
            )
            await db.commit()
            logger.info(f"단지 추가: {name} ({complex_no})")
            return True
        except Exception as e:
            logger.error(f"단지 추가 실패: {e}")
            return False


async def remove_complex(complex_no: str) -> bool:
    """모니터링 단지 비활성화"""
    async with await get_db() as db:
        try:
            await db.execute(
                "UPDATE complexes SET active = 0 WHERE complex_no = ?",
                (complex_no,),
            )
            await db.commit()
            logger.info(f"단지 삭제: {complex_no}")
            return True
        except Exception as e:
            logger.error(f"단지 삭제 실패: {e}")
            return False


async def get_active_complexes() -> list[dict]:
    """활성 모니터링 단지 목록"""
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT complex_no, name, address, added_at FROM complexes WHERE active = 1"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def find_complex_by_name(name: str) -> dict | None:
    """단지명으로 검색"""
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT complex_no, name, address FROM complexes WHERE name LIKE ? AND active = 1",
            (f"%{name}%",),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


# ==================== Articles ====================


async def upsert_article(
    article_no: str,
    complex_no: str,
    article_name: str = "",
    dong: str = "",
    ho: str = "",
    exclusive_area: float = 0.0,
    supply_area: float = 0.0,
    deal_price: int = 0,
    floor: str = "",
    direction: str = "",
    realtor_name: str = "",
    article_url: str = "",
    group_key: str = "",
) -> dict | None:
    """매물 삽입 또는 업데이트. 가격 변동 시 이전 가격 반환"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with await get_db() as db:
        # 기존 매물 확인
        cursor = await db.execute(
            "SELECT deal_price, is_active FROM articles WHERE article_no = ?",
            (article_no,),
        )
        existing = await cursor.fetchone()

        if existing:
            old_price = existing["deal_price"]
            was_active = existing["is_active"]

            # 업데이트
            await db.execute(
                """UPDATE articles SET
                    article_name = ?, dong = ?, ho = ?,
                    exclusive_area = ?, supply_area = ?,
                    deal_price = ?, floor = ?, direction = ?,
                    realtor_name = ?, article_url = ?,
                    last_seen_at = ?, is_active = 1, group_key = ?
                WHERE article_no = ?""",
                (
                    article_name, dong, ho,
                    exclusive_area, supply_area,
                    deal_price, floor, direction,
                    realtor_name, article_url,
                    now, group_key, article_no,
                ),
            )

            # 가격 변동 기록
            if old_price != deal_price and old_price > 0 and deal_price > 0:
                await db.execute(
                    "INSERT INTO price_history (article_no, old_price, new_price) VALUES (?, ?, ?)",
                    (article_no, old_price, deal_price),
                )
                await db.commit()
                return {"type": "price_change", "old_price": old_price, "new_price": deal_price}

            # 재등장 (이전에 삭제됐다가 다시 나온 매물)
            if not was_active:
                await db.commit()
                return {"type": "reappeared"}

            await db.commit()
            return None  # 변동 없음
        else:
            # 신규 매물
            await db.execute(
                """INSERT INTO articles
                    (article_no, complex_no, article_name, dong, ho,
                     exclusive_area, supply_area, deal_price, floor,
                     direction, realtor_name, article_url,
                     first_seen_at, last_seen_at, is_active, group_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                (
                    article_no, complex_no, article_name, dong, ho,
                    exclusive_area, supply_area, deal_price, floor,
                    direction, realtor_name, article_url,
                    now, now, group_key,
                ),
            )
            await db.commit()
            return {"type": "new"}


async def mark_removed_articles(complex_no: str, active_article_nos: set[str]) -> list[dict]:
    """스캔에서 사라진 매물을 비활성화하고 반환"""
    removed = []
    async with await get_db() as db:
        cursor = await db.execute(
            "SELECT article_no, dong, ho, exclusive_area, deal_price, first_seen_at "
            "FROM articles WHERE complex_no = ? AND is_active = 1",
            (complex_no,),
        )
        active_in_db = await cursor.fetchall()

        for row in active_in_db:
            if row["article_no"] not in active_article_nos:
                await db.execute(
                    "UPDATE articles SET is_active = 0, last_seen_at = datetime('now', 'localtime') "
                    "WHERE article_no = ?",
                    (row["article_no"],),
                )
                removed.append(dict(row))

        await db.commit()
    return removed


async def get_active_articles(complex_no: str | None = None) -> list[dict]:
    """활성 매물 목록 조회"""
    async with await get_db() as db:
        if complex_no:
            cursor = await db.execute(
                "SELECT * FROM articles WHERE complex_no = ? AND is_active = 1 ORDER BY dong, ho",
                (complex_no,),
            )
        else:
            cursor = await db.execute(
                "SELECT a.*, c.name as complex_name FROM articles a "
                "JOIN complexes c ON a.complex_no = c.complex_no "
                "WHERE a.is_active = 1 AND c.active = 1 ORDER BY c.name, a.dong, a.ho"
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_price_history(dong: str = "", ho: str = "", complex_no: str | None = None) -> list[dict]:
    """가격 변동 이력 조회"""
    async with await get_db() as db:
        query = """
            SELECT ph.*, a.dong, a.ho, a.exclusive_area, a.complex_no, c.name as complex_name
            FROM price_history ph
            JOIN articles a ON ph.article_no = a.article_no
            JOIN complexes c ON a.complex_no = c.complex_no
            WHERE 1=1
        """
        params = []

        if dong:
            query += " AND a.dong LIKE ?"
            params.append(f"%{dong}%")
        if ho:
            query += " AND a.ho LIKE ?"
            params.append(f"%{ho}%")
        if complex_no:
            query += " AND a.complex_no = ?"
            params.append(complex_no)

        query += " ORDER BY ph.changed_at DESC LIMIT 20"

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def has_any_articles() -> bool:
    """DB에 매물이 하나라도 있는지 확인 (초기 스캔 감지용)"""
    async with await get_db() as db:
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM articles")
        row = await cursor.fetchone()
        return row["cnt"] > 0
