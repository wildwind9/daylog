package com.daylog.controller;

import com.daylog.dto.ApiResponse;
import com.daylog.dto.LoginRequest;
import com.daylog.entity.AppUser;
import com.daylog.repository.AppUserRepository;
import com.daylog.service.CurrentUserService;
import com.daylog.service.weather.WeatherSyncService;
import com.daylog.security.JwtTokenProvider;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.ResponseEntity;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
@Tag(name = "Auth", description = "Authentication API")
public class AuthController {

    private final JwtTokenProvider jwtTokenProvider;
    private final AppUserRepository appUserRepository;
    private final PasswordEncoder passwordEncoder;
    private final CurrentUserService currentUserService;
    private final WeatherSyncService weatherSyncService;

    @Value("${daylog.admin.username}")
    private String adminUsername;

    @Value("${daylog.admin.password}")
    private String adminPassword;

    @PostMapping("/login")
    @Operation(summary = "Login", description = "Returns a JWT token")
    public ResponseEntity<ApiResponse<Map<String, String>>> login(
            @Valid @RequestBody LoginRequest request) {
        String username = normalizeUsername(request.getUsername());

        AppUser user = appUserRepository.findByUsernameIgnoreCase(username).orElse(null);
        if (isConfiguredAdminLogin(username, request.getPassword())) {
            user = ensureDefaultAdminAccount();
        }

        if (user == null
                || !user.isEnabled()
                || !passwordEncoder.matches(request.getPassword(), user.getPasswordHash())) {
            return ResponseEntity.status(401).body(ApiResponse.fail("用户名或密码错误"));
        }

        String token = jwtTokenProvider.generateToken(user.getId(), user.getUsername(), user.getRole());
        return ResponseEntity.ok(ApiResponse.ok(Map.of("token", token)));
    }

    @PostMapping("/register")
    @Operation(summary = "Register", description = "Creates a user and returns a JWT token")
    public ResponseEntity<ApiResponse<Map<String, String>>> register(
            @Valid @RequestBody LoginRequest request) {
        String username = normalizeUsername(request.getUsername());

        if (appUserRepository.existsByUsernameIgnoreCase(username)) {
            return ResponseEntity.status(409).body(ApiResponse.fail("用户名已存在"));
        }

        AppUser user = new AppUser();
        user.setUsername(username);
        user.setPasswordHash(passwordEncoder.encode(request.getPassword()));
        user.setRole("USER");
        user.setEnabled(true);

        try {
            AppUser savedUser = appUserRepository.save(user);
            String token = jwtTokenProvider.generateToken(savedUser.getId(), savedUser.getUsername(), savedUser.getRole());
            return ResponseEntity.ok(ApiResponse.ok(Map.of("token", token)));
        } catch (DataIntegrityViolationException e) {
            return ResponseEntity.status(409).body(ApiResponse.fail("用户名已存在"));
        }
    }

    @GetMapping("/me")
    @Operation(summary = "Get current user", description = "Returns the currently authenticated user")
    public ResponseEntity<ApiResponse<Map<String, Object>>> me() {
        AppUser user = currentUserService.currentUser();
        return ResponseEntity.ok(ApiResponse.ok(currentUserPayload(user)));
    }

    @PutMapping("/me/location")
    @Operation(summary = "Update current user location", description = "Updates the current user's saved location")
    public ResponseEntity<ApiResponse<Map<String, Object>>> updateLocation(
            @Valid @RequestBody LocationRequest request) {
        AppUser user = currentUserService.currentUser();
        user.setProvince(normalizeNullable(request.getProvince()));
        user.setCity(normalizeNullable(request.getCity()));
        user.setDistrict(normalizeNullable(request.getDistrict()));
        user.setLatitude(request.getLatitude());
        user.setLongitude(request.getLongitude());
        user.setLocationUpdatedAt(LocalDateTime.now());
        AppUser saved = appUserRepository.save(user);

        weatherSyncService.syncWeatherForDate(saved.getId(), LocalDate.now(ZoneId.of("Asia/Shanghai")));
        return ResponseEntity.ok(ApiResponse.ok(currentUserPayload(saved)));
    }

    private String normalizeUsername(String username) {
        return username == null ? "" : username.trim();
    }

    private boolean isConfiguredAdminLogin(String username, String password) {
        return adminUsername.equalsIgnoreCase(username) && adminPassword.equals(password);
    }

    private AppUser ensureDefaultAdminAccount() {
        AppUser user = appUserRepository.findByUsernameIgnoreCase(adminUsername)
                .orElseGet(AppUser::new);
        boolean needsSave = user.getId() == null
                || !adminUsername.equals(user.getUsername())
                || !"ADMIN".equals(user.getRole())
                || !user.isEnabled()
                || user.getPasswordHash() == null
                || !passwordEncoder.matches(adminPassword, user.getPasswordHash());

        if (!needsSave) {
            return user;
        }

        user.setUsername(adminUsername);
        user.setPasswordHash(passwordEncoder.encode(adminPassword));
        user.setRole("ADMIN");
        user.setEnabled(true);
        return appUserRepository.save(user);
    }

    private Map<String, Object> currentUserPayload(AppUser user) {
        Map<String, Object> payload = new HashMap<>();
        payload.put("id", user.getId());
        payload.put("username", user.getUsername());
        payload.put("role", user.getRole());
        payload.put("province", user.getProvince());
        payload.put("city", user.getCity());
        payload.put("district", user.getDistrict());
        payload.put("latitude", user.getLatitude());
        payload.put("longitude", user.getLongitude());
        payload.put("locationUpdatedAt", user.getLocationUpdatedAt());
        return payload;
    }

    private String normalizeNullable(String value) {
        String normalized = normalizeUsername(value);
        return normalized.isBlank() ? null : normalized;
    }

    public static class LocationRequest {
        private String province;
        private String city;
        private String district;
        private Double latitude;
        private Double longitude;

        public String getProvince() {
            return province;
        }

        public void setProvince(String province) {
            this.province = province;
        }

        public String getCity() {
            return city;
        }

        public void setCity(String city) {
            this.city = city;
        }

        public String getDistrict() {
            return district;
        }

        public void setDistrict(String district) {
            this.district = district;
        }

        public Double getLatitude() {
            return latitude;
        }

        public void setLatitude(Double latitude) {
            this.latitude = latitude;
        }

        public Double getLongitude() {
            return longitude;
        }

        public void setLongitude(Double longitude) {
            this.longitude = longitude;
        }
    }
}
