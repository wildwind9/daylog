package com.daylog.repository;

import com.daylog.entity.ContentItem;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.List;

public interface ContentItemRepository extends JpaRepository<ContentItem, Long> {

    boolean existsByUserIdAndSourceAndSourceId(Long userId, ContentItem.Source source, String sourceId);

    List<ContentItem> findByUserIdAndItemDateOrderByItemTimeAsc(Long userId, LocalDate itemDate);

    @Query("SELECT DISTINCT c.itemDate FROM ContentItem c " +
            "WHERE c.userId = :userId AND YEAR(c.itemDate) = :year AND MONTH(c.itemDate) = :month " +
            "ORDER BY c.itemDate")
    List<LocalDate> findActiveDatesByUserIdAndYearAndMonth(@Param("userId") Long userId,
                                                           @Param("year") int year,
                                                           @Param("month") int month);

    @Query("SELECT DISTINCT c FROM ContentItem c " +
            "WHERE c.userId = :userId AND (" +
            "LOWER(COALESCE(c.title, '')) LIKE LOWER(CONCAT('%', :query, '%')) OR " +
            "LOWER(COALESCE(c.body, '')) LIKE LOWER(CONCAT('%', :query, '%'))) " +
            "ORDER BY c.itemTime DESC")
    List<ContentItem> searchByUserIdAndQuery(@Param("userId") Long userId,
                                             @Param("query") String query);

    @Query("SELECT DISTINCT c FROM ContentTag ct " +
            "JOIN ct.contentItem c " +
            "JOIN ct.tag t " +
            "WHERE c.userId = :userId AND LOWER(t.name) LIKE LOWER(CONCAT('%', :query, '%')) " +
            "ORDER BY c.itemTime DESC")
    List<ContentItem> searchByUserIdAndTagName(@Param("userId") Long userId,
                                               @Param("query") String query);

    long countByUserIdAndSourceAndBindingId(Long userId, ContentItem.Source source, Long bindingId);

    long countByUserIdAndSource(Long userId, ContentItem.Source source);

    @Modifying
    @Transactional
    long deleteByUserIdAndSourceAndBindingId(Long userId, ContentItem.Source source, Long bindingId);
}
