package com.daylog.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Entity
@Table(name = "platform_config")
@Getter @Setter @NoArgsConstructor
public class PlatformConfig {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 20)
    private String platform;

    @Column(nullable = false)
    private boolean enabled = false;

    @Column(columnDefinition = "JSON")
    private String config;

    @Column(name = "last_sync")
    private LocalDateTime lastSync;
}
