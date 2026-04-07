package com.daylog.repository;

import com.daylog.entity.DiaryEntry;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

public interface DiaryEntryRepository extends JpaRepository<DiaryEntry, Long> {
    Optional<DiaryEntry> findByEntryDate(LocalDate entryDate);

    @Query("SELECT DISTINCT d.entryDate FROM DiaryEntry d " +
           "WHERE YEAR(d.entryDate) = :year AND MONTH(d.entryDate) = :month " +
           "ORDER BY d.entryDate")
    List<LocalDate> findActiveDatesByYearAndMonth(@Param("year") int year,
                                                  @Param("month") int month);
}
