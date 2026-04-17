package com.daylog.repository;

import com.daylog.entity.DiaryEntry;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

public interface DiaryEntryRepository extends JpaRepository<DiaryEntry, Long> {
    Optional<DiaryEntry> findByUserIdAndEntryDate(Long userId, LocalDate entryDate);

    @Query("SELECT DISTINCT d.entryDate FROM DiaryEntry d " +
            "WHERE d.userId = :userId AND YEAR(d.entryDate) = :year AND MONTH(d.entryDate) = :month " +
            "ORDER BY d.entryDate")
    List<LocalDate> findActiveDatesByUserIdAndYearAndMonth(@Param("userId") Long userId,
                                                           @Param("year") int year,
                                                           @Param("month") int month);

    @Query("SELECT d FROM DiaryEntry d " +
            "WHERE d.userId = :userId AND (" +
            "LOWER(COALESCE(d.mood, '')) LIKE LOWER(CONCAT('%', :query, '%')) OR " +
            "LOWER(COALESCE(d.weather, '')) LIKE LOWER(CONCAT('%', :query, '%'))) " +
            "ORDER BY d.entryDate DESC")
    List<DiaryEntry> searchByUserIdAndQuery(@Param("userId") Long userId,
                                            @Param("query") String query);
}
