"""数据库操作：将爬虫结果和标签写入 MySQL"""
import json
import os
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(os.getenv("DB_URL"), pool_pre_ping=True)
    return _engine


def get_latest_source_id(platform: str) -> str | None:
    """获取该平台最近一条记录的 source_id，用于增量抓取"""
    with Session(get_engine()) as session:
        row = session.execute(
            text("SELECT source_id FROM content_item "
                 "WHERE source = :platform AND source_id IS NOT NULL "
                 "ORDER BY item_time DESC LIMIT 1"),
            {"platform": platform},
        ).fetchone()
        return row[0] if row else None


def save_items(items: list[dict]) -> int:
    """批量插入内容，忽略重复（由 UNIQUE KEY 保证）。返回实际插入数量。"""
    if not items:
        return 0

    inserted = 0
    with Session(get_engine()) as session:
        for item in items:
            result = session.execute(
                text("""
                    INSERT INTO content_item
                        (source, source_id, source_url, content_type,
                         body, body_format, media, item_date, item_time, synced_at)
                    VALUES
                        (:source, :source_id, :source_url, :content_type,
                         :body, :body_format, :media, :item_date, :item_time, :synced_at)
                    ON DUPLICATE KEY UPDATE
                        source_url   = VALUES(source_url),
                        content_type = VALUES(content_type),
                        body         = VALUES(body),
                        body_format  = VALUES(body_format),
                        media        = VALUES(media),
                        synced_at    = VALUES(synced_at)
                """),
                {
                    "source":       item["source"],
                    "source_id":    item["source_id"],
                    "source_url":   item.get("source_url"),
                    "content_type": item.get("content_type", "text"),
                    "body":         item.get("body"),
                    "body_format":  item.get("body_format", "plain"),
                    "media":        json.dumps(item["media"], ensure_ascii=False)
                                    if item.get("media") else None,
                    "item_date":    item["item_date"],
                    "item_time":    item["item_time"],
                    "synced_at":    datetime.now(),
                },
            )
            inserted += result.rowcount
        session.commit()
    return inserted


def save_tags(item_id: int, tags: list[str], source: str = "llm") -> None:
    """为内容条目保存标签（tag 表 + content_tag 关联表）"""
    with Session(get_engine()) as session:
        for tag_name in tags:
            # 确保 tag 存在
            session.execute(
                text("INSERT IGNORE INTO tag (name) VALUES (:name)"),
                {"name": tag_name},
            )
            tag_row = session.execute(
                text("SELECT id FROM tag WHERE name = :name"),
                {"name": tag_name},
            ).fetchone()
            if tag_row:
                session.execute(
                    text("INSERT IGNORE INTO content_tag (item_id, tag_id, tag_source) "
                         "VALUES (:item_id, :tag_id, :source)"),
                    {"item_id": item_id, "tag_id": tag_row[0], "source": source},
                )
        session.commit()


def get_items_without_tags(platform: str, limit: int = 50) -> list[dict]:
    """获取尚未打标签的内容条目，用于异步分析"""
    with Session(get_engine()) as session:
        rows = session.execute(
            text("""
                SELECT ci.id, ci.body FROM content_item ci
                LEFT JOIN content_tag ct ON ci.id = ct.item_id
                WHERE ci.source = :platform AND ct.item_id IS NULL AND ci.body IS NOT NULL
                ORDER BY ci.item_time DESC LIMIT :limit
            """),
            {"platform": platform, "limit": limit},
        ).fetchall()
        return [{"id": r[0], "body": r[1]} for r in rows]
