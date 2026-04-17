package com.daylog.scheduler;

import com.daylog.service.weather.WeatherSyncService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@RequiredArgsConstructor
public class WeatherScheduler {

    private final WeatherSyncService weatherSyncService;

    @Scheduled(cron = "0 10 4 * * *", zone = "Asia/Shanghai")
    public void syncDailyWeather() {
        int updated = weatherSyncService.syncTodayWeatherForAllUsers();
        log.info("Weather sync complete, updated {} user(s)", updated);
    }
}
