package com.daylog.repository;

import com.daylog.entity.ContentItem;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDate;
import java.util.List;

public interface ContentItemRepository extends JpaRepository<ContentItem, Long> {

    boolean existsBySourceAndSourceId(ContentItem.Source source, String sourceId);

    List<ContentItem> findByItemDateOrderByItemTimeAsc(LocalDate itemDate);

    // 查询某月有内容的日期列表（去重）
    @Query("SELECT DISTINCT c.itemDate FROM ContentItem c " +
           "WHERE YEAR(c.itemDate) = :year AND MONTH(c.itemDate) = :month " +
           "ORDER BY c.itemDate")
    List<LocalDate> findActiveDatesByYearAndMonth(@Param("year") int year,
                                                  @Param("month") int month);
}
