package com.daylog.service.weather;

import com.daylog.entity.AppUser;
import com.daylog.entity.DiaryEntry;
import com.daylog.repository.AppUserRepository;
import com.daylog.repository.DiaryEntryRepository;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.time.ZoneId;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyDouble;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class WeatherSyncServiceTest {

    private static final ZoneId SHANGHAI = ZoneId.of("Asia/Shanghai");

    @Test
    void syncs_all_users_with_locations_for_today() {
        AppUserRepository appUserRepository = mock(AppUserRepository.class);
        DiaryEntryRepository diaryEntryRepository = mock(DiaryEntryRepository.class);
        WeatherFetcher weatherFetcher = mock(WeatherFetcher.class);
        LocalDate today = LocalDate.now(SHANGHAI);

        AppUser user = new AppUser();
        user.setId(9L);
        user.setLatitude(30.2);
        user.setLongitude(120.1);

        DiaryEntry entry = new DiaryEntry();
        entry.setUserId(9L);
        entry.setEntryDate(today);

        when(appUserRepository.findByLatitudeIsNotNullAndLongitudeIsNotNull()).thenReturn(List.of(user));
        when(appUserRepository.findById(9L)).thenReturn(Optional.of(user));
        when(diaryEntryRepository.findByUserIdAndEntryDate(9L, today)).thenReturn(Optional.of(entry));
        when(weatherFetcher.fetchWeatherLabel(anyDouble(), anyDouble())).thenReturn("sunny");

        WeatherSyncService service = new WeatherSyncService(appUserRepository, diaryEntryRepository, weatherFetcher);
        int updated = service.syncTodayWeatherForAllUsers();

        assertTrue(updated > 0);
        verify(diaryEntryRepository).save(entry);
    }

    @Test
    void syncs_today_weather_for_users_with_locations_only_when_weather_is_empty() {
        AppUserRepository appUserRepository = mock(AppUserRepository.class);
        DiaryEntryRepository diaryEntryRepository = mock(DiaryEntryRepository.class);
        WeatherFetcher weatherFetcher = mock(WeatherFetcher.class);
        LocalDate today = LocalDate.now(SHANGHAI);

        AppUser user = new AppUser();
        user.setId(7L);
        user.setLatitude(30.2);
        user.setLongitude(120.1);

        DiaryEntry entry = new DiaryEntry();
        entry.setUserId(7L);
        entry.setEntryDate(today);

        when(appUserRepository.findByLatitudeIsNotNullAndLongitudeIsNotNull()).thenReturn(List.of(user));
        when(appUserRepository.findById(7L)).thenReturn(Optional.of(user));
        when(diaryEntryRepository.findByUserIdAndEntryDate(7L, today)).thenReturn(Optional.of(entry));
        when(weatherFetcher.fetchWeatherLabel(anyDouble(), anyDouble())).thenReturn("light-rain");

        WeatherSyncService service = new WeatherSyncService(appUserRepository, diaryEntryRepository, weatherFetcher);
        boolean updated = service.syncWeatherForDate(7L, today);

        assertTrue(updated);
        verify(diaryEntryRepository).save(entry);
    }

    @Test
    void does_not_override_existing_manual_weather() {
        AppUserRepository appUserRepository = mock(AppUserRepository.class);
        DiaryEntryRepository diaryEntryRepository = mock(DiaryEntryRepository.class);
        WeatherFetcher weatherFetcher = mock(WeatherFetcher.class);
        LocalDate today = LocalDate.now(SHANGHAI);

        AppUser user = new AppUser();
        user.setId(8L);
        user.setLatitude(30.2);
        user.setLongitude(120.1);

        DiaryEntry entry = new DiaryEntry();
        entry.setUserId(8L);
        entry.setEntryDate(today);
        entry.setWeather("sunny");

        when(appUserRepository.findById(8L)).thenReturn(Optional.of(user));
        when(diaryEntryRepository.findByUserIdAndEntryDate(8L, today)).thenReturn(Optional.of(entry));
        when(weatherFetcher.fetchWeatherLabel(anyDouble(), anyDouble())).thenReturn("light-rain");

        WeatherSyncService service = new WeatherSyncService(appUserRepository, diaryEntryRepository, weatherFetcher);
        boolean updated = service.syncWeatherForDate(8L, today);

        assertFalse(updated);
        verify(diaryEntryRepository, never()).save(entry);
    }

    @Test
    void skips_users_without_coordinates() {
        AppUserRepository appUserRepository = mock(AppUserRepository.class);
        DiaryEntryRepository diaryEntryRepository = mock(DiaryEntryRepository.class);
        WeatherFetcher weatherFetcher = mock(WeatherFetcher.class);

        when(appUserRepository.findByLatitudeIsNotNullAndLongitudeIsNotNull()).thenReturn(List.of());

        WeatherSyncService service = new WeatherSyncService(appUserRepository, diaryEntryRepository, weatherFetcher);
        int updated = service.syncTodayWeatherForAllUsers();

        assertTrue(updated == 0);
        verify(weatherFetcher, never()).fetchWeatherLabel(anyDouble(), anyDouble());
        verify(diaryEntryRepository, never()).save(any(DiaryEntry.class));
    }
}
