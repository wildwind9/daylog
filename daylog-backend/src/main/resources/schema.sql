CREATE TABLE IF NOT EXISTS app_user (
    id            BIGINT       NOT NULL AUTO_INCREMENT,
    username      VARCHAR(50)  NOT NULL,
    password_hash VARCHAR(100) NOT NULL,
    role          VARCHAR(20)  NOT NULL DEFAULT 'USER',
    enabled       TINYINT(1)   NOT NULL DEFAULT 1,
    province      VARCHAR(100) NULL,
    city          VARCHAR(100) NULL,
    district      VARCHAR(100) NULL,
    latitude      DOUBLE       NULL,
    longitude     DOUBLE       NULL,
    location_updated_at DATETIME NULL,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_app_user_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SET @daylog_has_province := (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'app_user'
      AND COLUMN_NAME = 'province'
);
SET @daylog_sql := IF(@daylog_has_province = 0,
    'ALTER TABLE app_user ADD COLUMN province VARCHAR(100) NULL AFTER enabled',
    'SELECT 1');
PREPARE daylog_stmt FROM @daylog_sql;
EXECUTE daylog_stmt;
DEALLOCATE PREPARE daylog_stmt;

SET @daylog_has_city := (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'app_user'
      AND COLUMN_NAME = 'city'
);
SET @daylog_sql := IF(@daylog_has_city = 0,
    'ALTER TABLE app_user ADD COLUMN city VARCHAR(100) NULL AFTER province',
    'SELECT 1');
PREPARE daylog_stmt FROM @daylog_sql;
EXECUTE daylog_stmt;
DEALLOCATE PREPARE daylog_stmt;

SET @daylog_has_district := (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'app_user'
      AND COLUMN_NAME = 'district'
);
SET @daylog_sql := IF(@daylog_has_district = 0,
    'ALTER TABLE app_user ADD COLUMN district VARCHAR(100) NULL AFTER city',
    'SELECT 1');
PREPARE daylog_stmt FROM @daylog_sql;
EXECUTE daylog_stmt;
DEALLOCATE PREPARE daylog_stmt;

SET @daylog_has_latitude := (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'app_user'
      AND COLUMN_NAME = 'latitude'
);
SET @daylog_sql := IF(@daylog_has_latitude = 0,
    'ALTER TABLE app_user ADD COLUMN latitude DOUBLE NULL AFTER district',
    'SELECT 1');
PREPARE daylog_stmt FROM @daylog_sql;
EXECUTE daylog_stmt;
DEALLOCATE PREPARE daylog_stmt;

SET @daylog_has_longitude := (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'app_user'
      AND COLUMN_NAME = 'longitude'
);
SET @daylog_sql := IF(@daylog_has_longitude = 0,
    'ALTER TABLE app_user ADD COLUMN longitude DOUBLE NULL AFTER latitude',
    'SELECT 1');
PREPARE daylog_stmt FROM @daylog_sql;
EXECUTE daylog_stmt;
DEALLOCATE PREPARE daylog_stmt;

SET @daylog_has_location_updated_at := (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'app_user'
      AND COLUMN_NAME = 'location_updated_at'
);
SET @daylog_sql := IF(@daylog_has_location_updated_at = 0,
    'ALTER TABLE app_user ADD COLUMN location_updated_at DATETIME NULL AFTER longitude',
    'SELECT 1');
PREPARE daylog_stmt FROM @daylog_sql;
EXECUTE daylog_stmt;
DEALLOCATE PREPARE daylog_stmt;

CREATE TABLE IF NOT EXISTS content_item (
    id           BIGINT       NOT NULL AUTO_INCREMENT,
    user_id      BIGINT       NOT NULL,
    binding_id   BIGINT,
    source       VARCHAR(20)  NOT NULL,
    source_id    VARCHAR(128),
    source_url   VARCHAR(512),
    content_type VARCHAR(20)  NOT NULL,
    title        VARCHAR(512),
    body         LONGTEXT,
    body_format  VARCHAR(20)  NOT NULL DEFAULT 'plain',
    media        JSON,
    item_date    DATE         NOT NULL,
    item_time    DATETIME     NOT NULL,
    synced_at    DATETIME,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_user_source_item (user_id, source, source_id),
    INDEX idx_user_item_date (user_id, item_date),
    INDEX idx_user_source (user_id, source),
    INDEX idx_user_binding (user_id, binding_id),
    CONSTRAINT fk_content_item_user FOREIGN KEY (user_id) REFERENCES app_user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS weibo_binding (
    id          BIGINT       NOT NULL AUTO_INCREMENT,
    user_id     BIGINT       NOT NULL,
    weibo_uid   VARCHAR(64)  NOT NULL,
    screen_name VARCHAR(128) NULL,
    access_token VARCHAR(512) NULL,
    refresh_token VARCHAR(512) NULL,
    expires_at  DATETIME     NULL,
    active      TINYINT(1)   NOT NULL DEFAULT 1,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    unbound_at  DATETIME     NULL,
    PRIMARY KEY (id),
    INDEX idx_weibo_binding_user (user_id),
    INDEX idx_weibo_binding_user_active (user_id, active),
    INDEX idx_weibo_binding_user_uid (user_id, weibo_uid),
    CONSTRAINT fk_weibo_binding_user FOREIGN KEY (user_id) REFERENCES app_user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS diary_entry (
    id         BIGINT    NOT NULL AUTO_INCREMENT,
    user_id    BIGINT    NOT NULL,
    entry_date DATE      NOT NULL,
    mood       VARCHAR(20),
    weather    VARCHAR(20),
    updated_at DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_user_entry_date (user_id, entry_date),
    CONSTRAINT fk_diary_entry_user FOREIGN KEY (user_id) REFERENCES app_user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS tag (
    id         BIGINT      NOT NULL AUTO_INCREMENT,
    name       VARCHAR(50) NOT NULL,
    created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_tag_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS content_tag (
    item_id    BIGINT      NOT NULL,
    tag_id     BIGINT      NOT NULL,
    tag_source VARCHAR(20) NOT NULL,
    PRIMARY KEY (item_id, tag_id),
    FOREIGN KEY (item_id) REFERENCES content_item(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id)  REFERENCES tag(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS platform_config (
    id        BIGINT       NOT NULL AUTO_INCREMENT,
    user_id   BIGINT       NOT NULL,
    platform  VARCHAR(20)  NOT NULL,
    enabled   TINYINT(1)   NOT NULL DEFAULT 0,
    config    JSON,
    last_sync DATETIME,
    PRIMARY KEY (id),
    UNIQUE KEY uq_user_platform (user_id, platform),
    CONSTRAINT fk_platform_config_user FOREIGN KEY (user_id) REFERENCES app_user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sync_log (
    id         BIGINT       NOT NULL AUTO_INCREMENT,
    user_id    BIGINT       NOT NULL,
    platform   VARCHAR(20)  NOT NULL,
    synced_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    new_count  INT          NOT NULL DEFAULT 0,
    status     VARCHAR(10)  NOT NULL,
    error_msg  TEXT,
    PRIMARY KEY (id),
    INDEX idx_sync_user_platform (user_id, platform),
    INDEX idx_sync_time (synced_at),
    CONSTRAINT fk_sync_log_user FOREIGN KEY (user_id) REFERENCES app_user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
