package com.daylog.controller;

import com.daylog.dto.ApiResponse;
import com.daylog.entity.AppUser;
import com.daylog.repository.AppUserRepository;
import com.daylog.security.JwtTokenProvider;
import com.daylog.service.CurrentUserService;
import com.daylog.service.weather.WeatherSyncService;
import org.junit.jupiter.api.Test;
import org.springframework.http.ResponseEntity;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.time.LocalDate;
import java.time.ZoneId;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AuthControllerLocationTest {

    @Test
    void update_location_persists_coordinates_and_triggers_weather_sync() {
        JwtTokenProvider jwtTokenProvider = mock(JwtTokenProvider.class);
        AppUserRepository appUserRepository = mock(AppUserRepository.class);
        PasswordEncoder passwordEncoder = mock(PasswordEncoder.class);
        CurrentUserService currentUserService = mock(CurrentUserService.class);
        WeatherSyncService weatherSyncService = mock(WeatherSyncService.class);

        AppUser currentUser = new AppUser();
        currentUser.setId(42L);
        currentUser.setUsername("alice");
        currentUser.setRole("USER");
        currentUser.setEnabled(true);

        when(currentUserService.currentUser()).thenReturn(currentUser);
        when(appUserRepository.save(any(AppUser.class))).thenAnswer(invocation -> invocation.getArgument(0));
        when(weatherSyncService.syncWeatherForDate(eq(42L), any(LocalDate.class))).thenReturn(true);

        AuthController controller = new AuthController(
                jwtTokenProvider,
                appUserRepository,
                passwordEncoder,
                currentUserService,
                weatherSyncService);

        AuthController.LocationRequest request = new AuthController.LocationRequest();
        request.setProvince("Zhejiang");
        request.setCity("Hangzhou");
        request.setDistrict("Xihu");
        request.setLatitude(30.2);
        request.setLongitude(120.1);

        ResponseEntity<ApiResponse<Map<String, Object>>> response = controller.updateLocation(request);

        assertEquals(200, response.getStatusCode().value());
        verify(weatherSyncService).syncWeatherForDate(eq(42L), eq(LocalDate.now(ZoneId.of("Asia/Shanghai"))));

        ApiResponse<Map<String, Object>> body = response.getBody();
        assertNotNull(body);
        assertEquals("Zhejiang", body.getData().get("province"));
        assertEquals("Hangzhou", body.getData().get("city"));
        assertEquals("Xihu", body.getData().get("district"));
        assertEquals(30.2, ((Number) body.getData().get("latitude")).doubleValue());
        assertEquals(120.1, ((Number) body.getData().get("longitude")).doubleValue());
        assertNotNull(body.getData().get("locationUpdatedAt"));
    }
}
