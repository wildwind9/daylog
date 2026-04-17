package com.daylog.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;
import lombok.NoArgsConstructor;

import java.time.LocalDate;
import java.time.LocalDateTime;

@Entity
@Table(name = "content_item")
@Getter @Setter @NoArgsConstructor
public class ContentItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, columnDefinition = "varchar(20)")
    private Source source;

    @Column(name = "source_id", length = 128)
    private String sourceId;

    @Column(name = "source_url", length = 512)
    private String sourceUrl;

    @Enumerated(EnumType.STRING)
    @Column(name = "content_type", nullable = false, columnDefinition = "varchar(20)")
    private ContentType contentType;

    @Column(length = 512)
    private String title;

    @Column(columnDefinition = "LONGTEXT")
    private String body;

    @Enumerated(EnumType.STRING)
    @Column(name = "body_format", nullable = false, columnDefinition = "varchar(20)")
    private BodyFormat bodyFormat = BodyFormat.plain;

    @Column(columnDefinition = "JSON")
    private String media;

    @Column(name = "item_date", nullable = false)
    private LocalDate itemDate;

    @Column(name = "item_time", nullable = false)
    private LocalDateTime itemTime;

    @Column(name = "synced_at")
    private LocalDateTime syncedAt;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt = LocalDateTime.now();

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Column(name = "binding_id")
    private Long bindingId;

    public enum Source {
        weibo, douyin, xiaohongshu, manual
    }

    public enum ContentType {
        text, image, video, link, rich_text
    }

    public enum BodyFormat {
        plain, html, tiptap_json
    }
}
