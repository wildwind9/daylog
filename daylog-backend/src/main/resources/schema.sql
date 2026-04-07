-- Daylog 数据库建表脚本
-- 执行前请先创建数据库: CREATE DATABASE daylog CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ============================================================
-- 统一内容表（核心表，所有平台内容归一）
-- ============================================================
CREATE TABLE IF NOT EXISTS content_item (
    id           BIGINT       NOT NULL AUTO_INCREMENT,
    source       VARCHAR(20)  NOT NULL COMMENT '来源平台: weibo/douyin/xiaohongshu/manual',
    source_id    VARCHAR(128)          COMMENT '平台原始 ID，manual 类型为 NULL',
    source_url   VARCHAR(512)          COMMENT '原文链接',
    content_type VARCHAR(20)  NOT NULL COMMENT 'text/image/video/link/rich_text',
    title        VARCHAR(512)          COMMENT '标题（部分平台有）',
    body         LONGTEXT              COMMENT '正文内容',
    body_format  VARCHAR(20)  NOT NULL DEFAULT 'plain' COMMENT 'plain/html/tiptap_json',
    media        JSON                  COMMENT '图片/视频 URL 数组',
    item_date    DATE         NOT NULL COMMENT '发布日期，用于日历分组',
    item_time    DATETIME     NOT NULL COMMENT '发布时间',
    synced_at    DATETIME              COMMENT '同步时间，manual 类型为 NULL',
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_source_item (source, source_id),
    INDEX idx_item_date (item_date),
    INDEX idx_source (source)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='统一内容表';

-- ============================================================
-- 手动日记扩展信息（body 存 content_item，这里存情绪天气等）
-- ============================================================
CREATE TABLE IF NOT EXISTS diary_entry (
    id         BIGINT      NOT NULL AUTO_INCREMENT,
    entry_date DATE        NOT NULL COMMENT '日记日期',
    mood       VARCHAR(20)          COMMENT '情绪: happy/calm/sad/anxious/excited',
    weather    VARCHAR(20)          COMMENT '天气: sunny/cloudy/rainy/snowy',
    updated_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_entry_date (entry_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='手动日记扩展信息';

-- ============================================================
-- 标签表
-- ============================================================
CREATE TABLE IF NOT EXISTS tag (
    id         BIGINT      NOT NULL AUTO_INCREMENT,
    name       VARCHAR(50) NOT NULL COMMENT '标签名',
    created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_tag_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='标签';

-- ============================================================
-- 内容-标签关联
-- ============================================================
CREATE TABLE IF NOT EXISTS content_tag (
    item_id    BIGINT      NOT NULL,
    tag_id     BIGINT      NOT NULL,
    tag_source VARCHAR(20) NOT NULL COMMENT '打标来源: llm/local/manual',
    PRIMARY KEY (item_id, tag_id),
    FOREIGN KEY (item_id) REFERENCES content_item(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id)  REFERENCES tag(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='内容标签关联';

-- ============================================================
-- 平台配置（管理多平台同步状态）
-- ============================================================
CREATE TABLE IF NOT EXISTS platform_config (
    id        BIGINT       NOT NULL AUTO_INCREMENT,
    platform  VARCHAR(20)  NOT NULL COMMENT 'weibo/douyin/xiaohongshu',
    enabled   TINYINT(1)   NOT NULL DEFAULT 0,
    config    JSON                  COMMENT '平台配置（cookie、token 等）',
    last_sync DATETIME              COMMENT '最近一次成功同步时间',
    PRIMARY KEY (id),
    UNIQUE KEY uq_platform (platform)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='平台配置';

-- ============================================================
-- 同步日志
-- ============================================================
CREATE TABLE IF NOT EXISTS sync_log (
    id         BIGINT       NOT NULL AUTO_INCREMENT,
    platform   VARCHAR(20)  NOT NULL,
    synced_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    new_count  INT          NOT NULL DEFAULT 0,
    status     VARCHAR(10)  NOT NULL COMMENT 'success/failed',
    error_msg  TEXT,
    PRIMARY KEY (id),
    INDEX idx_sync_platform (platform),
    INDEX idx_sync_time (synced_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='同步日志';

-- ============================================================
-- 初始化平台配置
-- ============================================================
INSERT IGNORE INTO platform_config (platform, enabled) VALUES
    ('weibo',        0),
    ('douyin',       0),
    ('xiaohongshu',  0);
