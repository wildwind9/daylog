package com.daylog.controller;

import com.daylog.dto.ApiResponse;
import com.daylog.entity.ContentItem;
import com.daylog.entity.PlatformConfig;
import com.daylog.entity.WeiboBinding;
import com.daylog.repository.ContentItemRepository;
import com.daylog.repository.PlatformConfigRepository;
import com.daylog.repository.WeiboBindingRepository;
import com.daylog.security.JwtTokenProvider;
import com.daylog.service.CurrentUserService;
import com.daylog.service.WeiboOauthTicketService;
import com.fasterxml.jackson.databind.JsonNode;
import io.jsonwebtoken.JwtException;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.server.ResponseStatusException;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/weibo")
@RequiredArgsConstructor
@Tag(name = "Weibo", description = "Weibo binding and sync API")
@SecurityRequirement(name = "bearerAuth")
@Slf4j
public class WeiboController {

    private static final String WEIBO_AUTHORIZE_URL = "https://api.weibo.com/oauth2/authorize";
    private static final String WEIBO_ACCESS_TOKEN_URL = "https://api.weibo.com/oauth2/access_token";
    private static final String WEIBO_UID_URL = "https://api.weibo.com/2/account/get_uid.json";
    private static final String WEIBO_USER_SHOW_URL = "https://api.weibo.com/2/users/show.json";

    private final WebClient.Builder webClientBuilder;
    private final PlatformConfigRepository platformConfigRepository;
    private final CurrentUserService currentUserService;
    private final WeiboBindingRepository weiboBindingRepository;
    private final ContentItemRepository contentItemRepository;
    private final JwtTokenProvider jwtTokenProvider;
    private final WeiboOauthTicketService weiboOauthTicketService;

    @Value("${daylog.python-service.base-url}")
    private String pythonServiceUrl;

    @Value("${daylog.frontend-base-url}")
    private String frontendBaseUrl;

    @Value("${daylog.weibo.app-key:}")
    private String weiboAppKey;

    @Value("${daylog.weibo.app-secret:}")
    private String weiboAppSecret;

    @Value("${daylog.weibo.redirect-uri}")
    private String weiboRedirectUri;

    @GetMapping("/sync/status")
    @Operation(summary = "Get Weibo binding and sync status")
    public ApiResponse<Map<String, Object>> getSyncStatus() {
        Long userId = currentUserService.currentUserId();
        PlatformConfig config = getOrCreateWeiboConfig(userId);
        JsonNode loginStatus = getPython("/weibo/login/status?userId=" + userId);
        WeiboBinding activeBinding = weiboBindingRepository.findByUserIdAndActiveTrue(userId).orElse(null);
        boolean syncEnabled = config.isEnabled() && activeBinding != null;

        Map<String, Object> status = new HashMap<>();
        status.put("syncEnabled", syncEnabled);
        status.put("profileExists", loginStatus.path("profileExists").asBoolean(false));
        status.put("cookieConfigured", loginStatus.path("cookieConfigured").asBoolean(false));
        status.put("loginStateReady", loginStatus.path("loginStateReady").asBoolean(false));
        status.put("profileDir", loginStatus.path("profileDir").asText(""));
        status.put("activeBinding", activeBinding == null ? null : toBindingMap(activeBinding));
        status.put("totalWeiboContentCount", contentItemRepository.countByUserIdAndSource(userId, ContentItem.Source.weibo));
        return ApiResponse.ok(status);
    }

    @GetMapping("/oauth/start")
    @Operation(summary = "Start Weibo OAuth flow")
    public ApiResponse<Map<String, String>> startOauth() {
        Long userId = currentUserService.currentUserId();
        assertOauthConfigured();

        String state = jwtTokenProvider.generateWeiboOauthState(userId);
        String authorizeUrl = WEIBO_AUTHORIZE_URL
                + "?client_id=" + encode(weiboAppKey)
                + "&response_type=code"
                + "&redirect_uri=" + encode(weiboRedirectUri)
                + "&state=" + encode(state);

        return ApiResponse.ok(Map.of(
                "authorizeUrl", authorizeUrl,
                "redirectUri", weiboRedirectUri
        ));
    }

    @PostMapping("/login/qr")
    @Operation(summary = "Start QR-code login for Weibo web scraping")
    public ApiResponse<JsonNode> startQrLogin() {
        Long userId = currentUserService.currentUserId();
        return ApiResponse.ok(postPython("/weibo/login/qr?userId=" + userId, null));
    }

    @GetMapping("/login/qr")
    @Operation(summary = "Get QR-code login status for Weibo web scraping")
    public ApiResponse<JsonNode> getQrLoginStatus(@RequestParam(name = "sessionId") String sessionId) {
        Long userId = currentUserService.currentUserId();
        return ApiResponse.ok(getPython("/weibo/login/qr/" + encode(sessionId) + "?userId=" + userId));
    }

    @PostMapping("/bind/qr")
    @Transactional
    @Operation(summary = "Bind current user with Weibo account after QR web login")
    public ApiResponse<Map<String, Object>> bindWithQrLogin(@RequestBody BindQrLoginRequest request) {
        Long userId = currentUserService.currentUserId();
        if (request.weiboUid() == null || request.weiboUid().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "微博 UID 不能为空");
        }
        return ApiResponse.ok(activateBinding(
                userId,
                request.weiboUid(),
                request.screenName(),
                null,
                null,
                null,
                request.replaceExistingContent(),
                request.syncNow()
        ));
    }

    @GetMapping("/oauth/callback")
    @Operation(summary = "Handle Weibo OAuth callback")
    public org.springframework.http.ResponseEntity<Void> oauthCallback(
            @RequestParam(name = "code", required = false) String code,
            @RequestParam(name = "state", required = false) String state,
            @RequestParam(name = "error", required = false) String error,
            @RequestParam(name = "error_code", required = false) String errorCode) {
        if (error != null && !error.isBlank()) {
            return redirectToFrontend(buildCallbackUrl(
                    "error",
                    null,
                    null,
                    null,
                    "微博授权失败：" + error + (errorCode == null ? "" : " (" + errorCode + ")")
            ));
        }

        Long userId;
        try {
            userId = jwtTokenProvider.extractWeiboOauthStateUserId(state);
        } catch (JwtException | IllegalArgumentException ex) {
            return redirectToFrontend(buildCallbackUrl("error", null, null, null, "微博授权状态已失效，请重新发起绑定"));
        }

        try {
            JsonNode tokenData = exchangeOauthCode(code);
            String accessToken = tokenData.path("access_token").asText("");
            if (accessToken.isBlank()) {
                throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "微博 access token 获取失败");
            }

            String weiboUid = tokenData.path("uid").asText("");
            if (weiboUid.isBlank()) {
                weiboUid = fetchWeiboUid(accessToken);
            }
            if (weiboUid.isBlank()) {
                throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "微博 UID 获取失败");
            }

            String screenName = fetchWeiboScreenName(accessToken, weiboUid);
            String refreshToken = tokenData.path("refresh_token").asText("");
            long expiresIn = tokenData.path("expires_in").asLong(0L);
            LocalDateTime expiresAt = expiresIn > 0 ? LocalDateTime.now().plusSeconds(expiresIn) : null;
            String ticket = weiboOauthTicketService.create(
                    userId,
                    weiboUid,
                    screenName,
                    accessToken,
                    refreshToken,
                    expiresAt
            );

            return redirectToFrontend(buildCallbackUrl("success", ticket, weiboUid, screenName, null));
        } catch (Exception ex) {
            return redirectToFrontend(buildCallbackUrl("error", null, null, null, firstMessage(ex)));
        }
    }

    @PostMapping("/bind/confirm")
    @Transactional
    @Operation(summary = "Confirm Weibo OAuth binding")
    public ApiResponse<Map<String, Object>> confirmOauthBinding(@RequestBody ConfirmOauthBindingRequest request) {
        Long userId = currentUserService.currentUserId();
        WeiboOauthTicketService.PendingBinding pendingBinding = weiboOauthTicketService.consume(request.ticket(), userId);
        if (pendingBinding == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "微博绑定凭据已失效，请重新发起绑定");
        }

        return ApiResponse.ok(activateBinding(
                userId,
                pendingBinding.weiboUid(),
                pendingBinding.screenName(),
                pendingBinding.accessToken(),
                pendingBinding.refreshToken(),
                pendingBinding.tokenExpiresAt(),
                request.replaceExistingContent(),
                request.syncNow()
        ));
    }

    @PutMapping("/sync/enabled")
    @Operation(summary = "Enable or disable scheduled Weibo sync")
    public ApiResponse<Map<String, Object>> setSyncEnabled(@RequestBody SyncEnabledRequest request) {
        Long userId = currentUserService.currentUserId();
        PlatformConfig config = getOrCreateWeiboConfig(userId);
        if (request.enabled() && weiboBindingRepository.findByUserIdAndActiveTrue(userId).isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "请先绑定微博，再开启定时同步");
        }

        config.setEnabled(request.enabled());
        platformConfigRepository.save(config);
        return getSyncStatus();
    }

    @PostMapping("/sync/full")
    @Operation(summary = "Trigger full sync for the active Weibo binding")
    public ApiResponse<JsonNode> syncFull() {
        try {
            Long userId = currentUserService.currentUserId();
            WeiboBinding binding = requireActiveBinding(userId);
            return ApiResponse.ok(syncWeibo(userId, binding.getId(), true));
        } catch (ResponseStatusException exception) {
            throw exception;
        } catch (Exception exception) {
            log.error("Weibo full sync failed", exception);
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, firstMessage(exception), exception);
        }
    }

    @DeleteMapping("/bind/active")
    @Transactional
    @Operation(summary = "Unbind current Weibo account")
    public ApiResponse<Map<String, Object>> unbindActive(@RequestBody(required = false) UnbindBindingRequest request) {
        Long userId = currentUserService.currentUserId();
        boolean clearSyncedContent = request != null && request.clearSyncedContent();
        WeiboBinding activeBinding = weiboBindingRepository.findByUserIdAndActiveTrue(userId).orElse(null);
        PlatformConfig config = getOrCreateWeiboConfig(userId);

        Long removedContentCount = 0L;
        if (activeBinding != null) {
            activeBinding.setActive(false);
            activeBinding.setUnboundAt(LocalDateTime.now());
            activeBinding.setAccessToken(null);
            activeBinding.setRefreshToken(null);
            activeBinding.setExpiresAt(null);
            weiboBindingRepository.save(activeBinding);
            if (clearSyncedContent) {
                removedContentCount = contentItemRepository.deleteByUserIdAndSourceAndBindingId(
                        userId,
                        ContentItem.Source.weibo,
                        activeBinding.getId()
                );
            }
        }
        if (config.isEnabled()) {
            config.setEnabled(false);
            platformConfigRepository.save(config);
        }

        deletePython("/weibo/login/state?userId=" + userId);

        Map<String, Object> result = new HashMap<>();
        result.put("removedContentCount", removedContentCount);
        result.put("status", getSyncStatus().getData());
        return ApiResponse.ok(result);
    }

    private Map<String, Object> activateBinding(
            Long userId,
            String weiboUid,
            String screenName,
            String accessToken,
            String refreshToken,
            LocalDateTime expiresAt,
            boolean replaceExistingContent,
            boolean syncNow
    ) {
        WeiboBinding previousActive = weiboBindingRepository.findByUserIdAndActiveTrue(userId).orElse(null);
        WeiboBinding targetBinding = weiboBindingRepository
                .findTopByUserIdAndWeiboUidOrderByCreatedAtDesc(userId, weiboUid)
                .orElseGet(WeiboBinding::new);

        boolean reusedExistingBinding = targetBinding.getId() != null;
        targetBinding.setUserId(userId);
        targetBinding.setWeiboUid(weiboUid);
        targetBinding.setScreenName(screenName);
        targetBinding.setAccessToken(accessToken);
        targetBinding.setRefreshToken(refreshToken);
        targetBinding.setExpiresAt(expiresAt);
        targetBinding.setActive(true);
        targetBinding.setUnboundAt(null);
        targetBinding = weiboBindingRepository.save(targetBinding);

        Long removedContentCount = 0L;
        if (previousActive != null && !previousActive.getId().equals(targetBinding.getId())) {
            previousActive.setActive(false);
            previousActive.setUnboundAt(LocalDateTime.now());
            weiboBindingRepository.save(previousActive);

            if (replaceExistingContent) {
                removedContentCount = contentItemRepository.deleteByUserIdAndSourceAndBindingId(
                        userId,
                        ContentItem.Source.weibo,
                        previousActive.getId()
                );
            }
        }

        JsonNode syncResult = null;
        if (replaceExistingContent || syncNow) {
            syncResult = syncWeibo(userId, targetBinding.getId(), true);
        }

        Map<String, Object> result = new HashMap<>();
        result.put("activeBinding", toBindingMap(targetBinding));
        result.put("reusedExistingBinding", reusedExistingBinding);
        result.put("replacedContent", replaceExistingContent);
        result.put("removedContentCount", removedContentCount);
        result.put("syncResult", syncResult);
        result.put("status", getSyncStatus().getData());
        return result;
    }

    private PlatformConfig getOrCreateWeiboConfig(Long userId) {
        return platformConfigRepository.findByUserIdAndPlatform(userId, "weibo")
                .orElseGet(() -> {
                    PlatformConfig next = new PlatformConfig();
                    next.setPlatform("weibo");
                    next.setUserId(userId);
                    next.setEnabled(false);
                    return platformConfigRepository.save(next);
                });
    }

    private WeiboBinding requireActiveBinding(Long userId) {
        return weiboBindingRepository.findByUserIdAndActiveTrue(userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "当前没有已绑定的微博账号"));
    }

    private JsonNode syncWeibo(Long userId, Long bindingId, boolean full) {
        String path = "/scrape/weibo?userId=" + userId + "&bindingId=" + bindingId + "&full=" + full;
        return postPython(path, null);
    }

    private Map<String, Object> toBindingMap(WeiboBinding binding) {
        Map<String, Object> result = new HashMap<>();
        result.put("id", binding.getId());
        result.put("weiboUid", binding.getWeiboUid());
        result.put("screenName", binding.getScreenName());
        result.put("active", binding.isActive());
        result.put("createdAt", binding.getCreatedAt());
        result.put("unboundAt", binding.getUnboundAt());
        result.put("expiresAt", binding.getExpiresAt());
        result.put("contentCount", contentItemRepository.countByUserIdAndSourceAndBindingId(
                binding.getUserId(),
                ContentItem.Source.weibo,
                binding.getId()
        ));
        return result;
    }

    private JsonNode exchangeOauthCode(String code) {
        MultiValueMap<String, String> form = new LinkedMultiValueMap<>();
        form.add("client_id", weiboAppKey);
        form.add("client_secret", weiboAppSecret);
        form.add("grant_type", "authorization_code");
        form.add("code", code);
        form.add("redirect_uri", weiboRedirectUri);

        return webClientBuilder.build()
                .post()
                .uri(WEIBO_ACCESS_TOKEN_URL)
                .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                .body(BodyInserters.fromFormData(form))
                .retrieve()
                .bodyToMono(JsonNode.class)
                .block();
    }

    private String fetchWeiboUid(String accessToken) {
        JsonNode jsonNode = webClientBuilder.build()
                .get()
                .uri(WEIBO_UID_URL + "?access_token=" + encode(accessToken))
                .retrieve()
                .bodyToMono(JsonNode.class)
                .block();
        return jsonNode == null ? "" : jsonNode.path("uid").asText("");
    }

    private String fetchWeiboScreenName(String accessToken, String uid) {
        JsonNode jsonNode = webClientBuilder.build()
                .get()
                .uri(WEIBO_USER_SHOW_URL + "?access_token=" + encode(accessToken) + "&uid=" + encode(uid))
                .retrieve()
                .bodyToMono(JsonNode.class)
                .block();
        if (jsonNode == null) {
            return uid;
        }
        return jsonNode.path("screen_name").asText(uid);
    }

    private void assertOauthConfigured() {
        if (weiboAppKey == null || weiboAppKey.isBlank() || weiboAppSecret == null || weiboAppSecret.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "微博开放平台配置缺失，请先配置 App Key 和 App Secret");
        }
    }

    private org.springframework.http.ResponseEntity<Void> redirectToFrontend(String url) {
        return org.springframework.http.ResponseEntity.status(HttpStatus.FOUND)
                .header("Location", url)
                .build();
    }

    private String buildCallbackUrl(String status, String ticket, String uid, String screenName, String message) {
        StringBuilder builder = new StringBuilder(frontendBaseUrl).append("/weibo-callback?status=").append(encode(status));
        if (ticket != null && !ticket.isBlank()) {
            builder.append("&ticket=").append(encode(ticket));
        }
        if (uid != null && !uid.isBlank()) {
            builder.append("&uid=").append(encode(uid));
        }
        if (screenName != null && !screenName.isBlank()) {
            builder.append("&screenName=").append(encode(screenName));
        }
        if (message != null && !message.isBlank()) {
            builder.append("&message=").append(encode(message));
        }
        return builder.toString();
    }

    private String encode(String value) {
        return URLEncoder.encode(value == null ? "" : value, StandardCharsets.UTF_8);
    }

    private String firstMessage(Exception exception) {
        Throwable target = exception;
        while (target.getCause() != null) {
            target = target.getCause();
        }
        String message = target.getMessage();
        return message == null || message.isBlank() ? "微博绑定失败，请稍后重试" : message;
    }

    private JsonNode getPython(String path) {
        return webClientBuilder.build()
                .get()
                .uri(pythonServiceUrl + path)
                .retrieve()
                .bodyToMono(JsonNode.class)
                .block();
    }

    private JsonNode postPython(String path, Object body) {
        WebClient.RequestBodySpec request = webClientBuilder.build()
                .post()
                .uri(pythonServiceUrl + path);

        return (body == null ? request : request.bodyValue(body))
                .retrieve()
                .bodyToMono(JsonNode.class)
                .block();
    }

    private void deletePython(String path) {
        webClientBuilder.build()
                .delete()
                .uri(pythonServiceUrl + path)
                .retrieve()
                .bodyToMono(Void.class)
                .block();
    }

    public record SyncEnabledRequest(boolean enabled) {
    }

    public record ConfirmOauthBindingRequest(
            String ticket,
            boolean replaceExistingContent,
            boolean syncNow
    ) {
    }

    public record BindQrLoginRequest(
            String weiboUid,
            String screenName,
            boolean replaceExistingContent,
            boolean syncNow
    ) {
    }

    public record UnbindBindingRequest(boolean clearSyncedContent) {
    }
}
