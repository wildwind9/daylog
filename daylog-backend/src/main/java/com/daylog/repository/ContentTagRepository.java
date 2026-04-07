package com.daylog.repository;

import com.daylog.entity.ContentTag;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface ContentTagRepository extends JpaRepository<ContentTag, ContentTag.ContentTagId> {
    List<ContentTag> findByContentItemId(Long itemId);
    void deleteByContentItemId(Long itemId);
}
