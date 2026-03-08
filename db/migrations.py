"""
데이터베이스 테이블 생성 및 마이그레이션
"""

import logging

import aiosqlite

logger = logging.getLogger("cron-estate.db")

DB_PATH = "cron_estate.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS complexes (
    complex_no  TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    address     TEXT DEFAULT '',
    added_at    TEXT DEFAULT (datetime('now', 'localtime')),
    active      INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS articles (
    article_no      TEXT PRIMARY KEY,
    complex_no      TEXT NOT NULL,
    article_name    TEXT DEFAULT '',
    dong            TEXT DEFAULT '',
    ho              TEXT DEFAULT '',
    exclusive_area  REAL DEFAULT 0,
    supply_area     REAL DEFAULT 0,
    deal_price      INTEGER DEFAULT 0,
    floor           TEXT DEFAULT '',
    direction       TEXT DEFAULT '',
    realtor_name    TEXT DEFAULT '',
    article_url     TEXT DEFAULT '',
    first_seen_at   TEXT DEFAULT (datetime('now', 'localtime')),
    last_seen_at    TEXT DEFAULT (datetime('now', 'localtime')),
    is_active       INTEGER DEFAULT 1,
    group_key       TEXT DEFAULT '',
    FOREIGN KEY (complex_no) REFERENCES complexes(complex_no)
);

CREATE TABLE IF NOT EXISTS price_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    article_no  TEXT NOT NULL,
    old_price   INTEGER NOT NULL,
    new_price   INTEGER NOT NULL,
    changed_at  TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (article_no) REFERENCES articles(article_no)
);

CREATE INDEX IF NOT EXISTS idx_articles_complex ON articles(complex_no);
CREATE INDEX IF NOT EXISTS idx_articles_group_key ON articles(group_key);
CREATE INDEX IF NOT EXISTS idx_articles_active ON articles(is_active);
CREATE INDEX IF NOT EXISTS idx_price_history_article ON price_history(article_no);
"""


async def initialize_database():
    """데이터베이스 테이블 생성"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA_SQL)
        await db.commit()
    logger.info(f"데이터베이스 초기화 완료: {DB_PATH}")
