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


def get_latest_source_id(platform: str, user_id: int, binding_id: int | None = None) -> str | None:
    """获取该平台最近一条记录的 source_id，用于增量抓取"""
    with Session(get_engine()) as session:
        row = session.execute(
            text("SELECT source_id FROM content_item "
                 "WHERE source = :platform AND source_id IS NOT NULL "
                 "AND user_id = :user_id "
                 "AND (:binding_id IS NULL OR binding_id = :binding_id) "
                 "ORDER BY item_time DESC LIMIT 1"),
            {"platform": platform, "user_id": user_id, "binding_id": binding_id},
        ).fetchone()
        return row[0] if row else None


def get_weibo_binding_auth(user_id: int, binding_id: int | None = None) -> dict | None:
    with Session(get_engine()) as session:
        row = session.execute(
            text(
                "SELECT id, weibo_uid, screen_name, access_token, refresh_token, expires_at "
                "FROM weibo_binding "
                "WHERE user_id = :user_id "
                "AND (:binding_id IS NULL OR id = :binding_id) "
                "AND active = 1 "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"user_id": user_id, "binding_id": binding_id},
        ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "weibo_uid": row[1],
            "screen_name": row[2],
            "access_token": row[3],
            "refresh_token": row[4],
            "expires_at": row[5],
        }


def _parse_media_json(media_json: str | None) -> list[str] | None:
    if not media_json:
        return None
    try:
        parsed = json.loads(media_json)
    except (TypeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, list) and parsed else None


def _merge_item_with_existing(item: dict, existing: dict | None) -> dict:
    if not existing:
        return dict(item)

    merged = dict(item)
    if not merged.get("source_url") and existing.get("source_url"):
        merged["source_url"] = existing["source_url"]
    if not merged.get("title") and existing.get("title"):
        merged["title"] = existing["title"]
    if not merged.get("body") and existing.get("body"):
        merged["body"] = existing["body"]
    if not merged.get("body_format") and existing.get("body_format"):
        merged["body_format"] = existing["body_format"]

    existing_media = _parse_media_json(existing.get("media"))
    if not merged.get("media") and existing_media:
        merged["media"] = existing_media
        merged["content_type"] = existing.get("content_type") or merged.get("content_type") or "image"

    return merged


def _load_existing_items(session: Session, items: list[dict], user_id: int, binding_id: int | None = None) -> dict[str, dict]:
    source = next((item.get("source") for item in items if item.get("source")), None)
    source_ids = [item.get("source_id") for item in items if item.get("source_id")]
    if not source or not source_ids:
        return {}

    unique_source_ids = list(dict.fromkeys(source_ids))
    placeholders = []
    params = {"source": source, "user_id": user_id, "binding_id": binding_id}
    for index, source_id in enumerate(unique_source_ids):
        key = f"source_id_{index}"
        placeholders.append(f":{key}")
        params[key] = source_id

    rows = session.execute(
        text(
            f"""
                SELECT source_id, source_url, content_type, title, body, body_format, media
                FROM content_item
                WHERE user_id = :user_id
                  AND source = :source
                  AND source_id IN ({", ".join(placeholders)})
                  AND (:binding_id IS NULL OR binding_id = :binding_id)
            """
        ),
        params,
    ).fetchall()

    return {
        row[0]: {
            "source_url": row[1],
            "content_type": row[2],
            "title": row[3],
            "body": row[4],
            "body_format": row[5],
            "media": row[6],
        }
        for row in rows
    }


def save_items(items: list[dict], user_id: int, binding_id: int | None = None) -> int:
    """批量插入内容，忽略重复（由 UNIQUE KEY 保证）。返回实际插入数量。"""
    if not items:
        return 0

    inserted = 0
    with Session(get_engine()) as session:
        existing_items = _load_existing_items(session, items, user_id, binding_id=binding_id)
        for raw_item in items:
            item = _merge_item_with_existing(raw_item, existing_items.get(raw_item.get("source_id")))
            result = session.execute(
                text("""
                    INSERT INTO content_item
                        (source, source_id, source_url, content_type,
                         title, body, body_format, media, item_date, item_time, synced_at, user_id, binding_id)
                    VALUES
                        (:source, :source_id, :source_url, :content_type,
                         :title, :body, :body_format, :media, :item_date, :item_time, :synced_at, :user_id, :binding_id)
                    ON DUPLICATE KEY UPDATE
                        source_url   = VALUES(source_url),
                        content_type = VALUES(content_type),
                        title        = VALUES(title),
                        body         = VALUES(body),
                        body_format  = VALUES(body_format),
                        media        = VALUES(media),
                        synced_at    = VALUES(synced_at),
                        binding_id   = VALUES(binding_id)
                """),
                {
                    "source":       item["source"],
                    "source_id":    item["source_id"],
                    "source_url":   item.get("source_url"),
                    "content_type": item.get("content_type", "text"),
                    "title":        item.get("title"),
                    "body":         item.get("body"),
                    "body_format":  item.get("body_format", "plain"),
                    "media":        json.dumps(item["media"], ensure_ascii=False)
                                    if item.get("media") else None,
                    "item_date":    item["item_date"],
                    "item_time":    item["item_time"],
                    "synced_at":    datetime.now(),
                    "user_id":      user_id,
                    "binding_id":   binding_id if item["source"] == "weibo" else None,
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


def update_mood_for_item_date(item_id: int, mood: str) -> bool:
    """Set the diary mood for the item's date if the user has not chosen one."""
    if not mood:
        return False

    with Session(get_engine()) as session:
        item_row = session.execute(
            text("SELECT user_id, item_date FROM content_item WHERE id = :item_id"),
            {"item_id": item_id},
        ).fetchone()
        if not item_row:
            return False

        result = session.execute(
            text("""
                INSERT INTO diary_entry (user_id, entry_date, mood, updated_at)
                VALUES (:user_id, :entry_date, :mood, :updated_at)
                ON DUPLICATE KEY UPDATE
                    mood = IF(mood IS NULL OR mood = '', VALUES(mood), mood),
                    updated_at = updated_at
            """),
            {
                "user_id": item_row[0],
                "entry_date": item_row[1],
                "mood": mood,
                "updated_at": datetime.now(),
            },
        )
        session.commit()
        return result.rowcount > 0


def clear_tags_for_platform(platform: str, user_id: int) -> int:
    """Remove existing tag relations for a user's platform items before re-analysis."""
    with Session(get_engine()) as session:
        result = session.execute(
            text("""
                DELETE ct FROM content_tag ct
                JOIN content_item ci ON ci.id = ct.item_id
                WHERE ci.source = :platform AND ci.user_id = :user_id
            """),
            {"platform": platform, "user_id": user_id},
        )
        session.commit()
        return result.rowcount


def get_items_without_tags(platform: str, user_id: int, limit: int = 50) -> list[dict]:
    """获取尚未打标签的内容条目，用于异步分析"""
    with Session(get_engine()) as session:
        rows = session.execute(
            text("""
                SELECT ci.id, ci.body, ci.item_date FROM content_item ci
                LEFT JOIN content_tag ct ON ci.id = ct.item_id
                WHERE ci.source = :platform AND ci.user_id = :user_id
                  AND ct.item_id IS NULL AND ci.body IS NOT NULL
                ORDER BY ci.item_time DESC LIMIT :limit
            """),
            {"platform": platform, "user_id": user_id, "limit": limit},
        ).fetchall()
        return [{"id": r[0], "body": r[1], "item_date": r[2]} for r in rows]
