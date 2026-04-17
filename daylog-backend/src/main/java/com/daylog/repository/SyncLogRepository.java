package com.daylog.repository;

import com.daylog.entity.SyncLog;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface SyncLogRepository extends JpaRepository<SyncLog, Long> {
    List<SyncLog> findByUserIdAndPlatformOrderBySyncedAtDesc(Long userId, String platform, Pageable pageable);
}
