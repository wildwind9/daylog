package com.daylog.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;
import lombok.NoArgsConstructor;

import java.time.LocalDate;
import java.time.LocalDateTime;

@Entity
@Table(name = "diary_entry")
@Getter @Setter @NoArgsConstructor
public class DiaryEntry {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "entry_date", nullable = false, unique = true)
    private LocalDate entryDate;

    @Column(length = 20)
    private String mood;

    @Column(length = 20)
    private String weather;

    @Column(name = "updated_at")
    private LocalDateTime updatedAt = LocalDateTime.now();

    @Column(name = "user_id", nullable = false)
    private Long userId;
}
