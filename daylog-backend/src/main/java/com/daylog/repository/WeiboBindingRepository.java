package com.daylog.repository;

import com.daylog.entity.WeiboBinding;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface WeiboBindingRepository extends JpaRepository<WeiboBinding, Long> {
    Optional<WeiboBinding> findByUserIdAndActiveTrue(Long userId);
    Optional<WeiboBinding> findTopByUserIdAndWeiboUidOrderByCreatedAtDesc(Long userId, String weiboUid);
    List<WeiboBinding> findByUserIdOrderByCreatedAtDesc(Long userId);
}
