package com.daylog.controller;

import com.daylog.dto.ApiResponse;
import com.daylog.dto.LoginRequest;
import com.daylog.security.JwtTokenProvider;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
@Tag(name = "Auth", description = "认证接口")
public class AuthController {

    private final JwtTokenProvider jwtTokenProvider;

    @Value("${daylog.admin.username}")
    private String adminUsername;

    @Value("${daylog.admin.password}")
    private String adminPassword;

    @PostMapping("/login")
    @Operation(summary = "管理员登录", description = "返回 JWT Token")
    public ResponseEntity<ApiResponse<Map<String, String>>> login(
            @Valid @RequestBody LoginRequest request) {

        if (!adminUsername.equals(request.getUsername())
                || !adminPassword.equals(request.getPassword())) {
            return ResponseEntity.status(401)
                    .body(ApiResponse.fail("用户名或密码错误"));
        }

        String token = jwtTokenProvider.generateToken(request.getUsername());
        return ResponseEntity.ok(ApiResponse.ok(Map.of("token", token)));
    }
}
