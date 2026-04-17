package com.daylog.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Entity
@Table(name = "sync_log")
@Getter @Setter @NoArgsConstructor
public class SyncLog {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 20)
    private String platform;

    @Column(name = "synced_at", nullable = false)
    private LocalDateTime syncedAt = LocalDateTime.now();

    @Column(name = "new_count", nullable = false)
    private int newCount = 0;

    @Column(nullable = false, length = 10)
    private String status;

    @Column(name = "error_msg", columnDefinition = "TEXT")
    private String errorMsg;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    public static SyncLog success(Long userId, String platform, int newCount) {
        SyncLog log = new SyncLog();
        log.userId = userId;
        log.platform = platform;
        log.newCount = newCount;
        log.status = "success";
        return log;
    }

    public static SyncLog failed(Long userId, String platform, String errorMsg) {
        SyncLog log = new SyncLog();
        log.userId = userId;
        log.platform = platform;
        log.status = "failed";
        log.errorMsg = errorMsg;
        return log;
    }
}
