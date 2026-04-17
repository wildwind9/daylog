package com.daylog.repository;

import com.daylog.entity.PlatformConfig;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface PlatformConfigRepository extends JpaRepository<PlatformConfig, Long> {
    Optional<PlatformConfig> findByUserIdAndPlatform(Long userId, String platform);
    List<PlatformConfig> findByEnabledTrue();
}
