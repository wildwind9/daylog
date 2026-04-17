package com.daylog.service.weather;

import com.daylog.entity.AppUser;
import com.daylog.entity.DiaryEntry;
import com.daylog.repository.AppUserRepository;
import com.daylog.repository.DiaryEntryRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class WeatherSyncService {

    private static final ZoneId SHANGHAI = ZoneId.of("Asia/Shanghai");

    private final AppUserRepository appUserRepository;
    private final DiaryEntryRepository diaryEntryRepository;
    private final WeatherFetcher weatherFetcher;

    @Transactional
    public int syncTodayWeatherForAllUsers() {
        LocalDate today = LocalDate.now(SHANGHAI);
        List<AppUser> users = appUserRepository.findByLatitudeIsNotNullAndLongitudeIsNotNull();
        int updated = 0;
        for (AppUser user : users) {
            if (syncWeatherForDate(user.getId(), today)) {
                updated++;
            }
        }
        return updated;
    }

    @Transactional
    public boolean syncWeatherForToday(Long userId) {
        return syncWeatherForDate(userId, LocalDate.now(SHANGHAI));
    }

    @Transactional
    public boolean syncWeatherForDate(Long userId, LocalDate date) {
        return appUserRepository.findById(userId)
                .map(user -> syncWeatherForDate(user, date))
                .orElse(false);
    }

    @Transactional
    public boolean syncWeatherForDate(AppUser user, LocalDate date) {
        if (user.getLatitude() == null || user.getLongitude() == null) {
            return false;
        }

        try {
            String weather = weatherFetcher.fetchWeatherLabel(user.getLatitude(), user.getLongitude());
            if (weather == null || weather.isBlank()) {
                return false;
            }

            DiaryEntry entry = diaryEntryRepository.findByUserIdAndEntryDate(user.getId(), date)
                    .orElseGet(() -> {
                        DiaryEntry created = new DiaryEntry();
                        created.setUserId(user.getId());
                        created.setEntryDate(date);
                        return created;
                    });

            if (entry.getWeather() != null && !entry.getWeather().isBlank()) {
                return false;
            }

            entry.setWeather(weather);
            entry.setUpdatedAt(LocalDateTime.now());
            diaryEntryRepository.save(entry);
            return true;
        } catch (Exception e) {
            log.warn("Weather sync failed for user {} on {}: {}", user.getId(), date, e.getMessage());
            return false;
        }
    }
}
