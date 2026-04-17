package com.daylog.repository;

import com.daylog.entity.Tag;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

public interface TagRepository extends JpaRepository<Tag, Long> {
    Optional<Tag> findByName(String name);

    @Query("SELECT DISTINCT t FROM Tag t " +
            "JOIN ContentTag ct ON ct.tag = t " +
            "JOIN ContentItem ci ON ct.contentItem = ci " +
            "WHERE ci.userId = :userId AND ci.itemDate = :date")
    List<Tag> findTagsByUserIdAndDate(@Param("userId") Long userId,
                                      @Param("date") LocalDate date);
}
