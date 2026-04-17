package com.daylog.service;

import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class WeiboOauthTicketService {

    private static final Duration TTL = Duration.ofMinutes(10);

    private final Map<String, PendingBinding> tickets = new ConcurrentHashMap<>();

    public String create(
            Long userId,
            String weiboUid,
            String screenName,
            String accessToken,
            String refreshToken,
            LocalDateTime tokenExpiresAt
    ) {
        pruneExpired();
        String ticket = UUID.randomUUID().toString().replace("-", "");
        tickets.put(ticket, new PendingBinding(
                userId,
                weiboUid,
                screenName,
                accessToken,
                refreshToken,
                tokenExpiresAt,
                Instant.now().plus(TTL)
        ));
        return ticket;
    }

    public PendingBinding get(String ticket, Long userId) {
        pruneExpired();
        PendingBinding pendingBinding = tickets.get(ticket);
        if (pendingBinding == null || !pendingBinding.userId().equals(userId)) {
            return null;
        }
        return pendingBinding;
    }

    public PendingBinding consume(String ticket, Long userId) {
        pruneExpired();
        PendingBinding pendingBinding = tickets.remove(ticket);
        if (pendingBinding == null || !pendingBinding.userId().equals(userId)) {
            return null;
        }
        return pendingBinding;
    }

    private void pruneExpired() {
        Instant now = Instant.now();
        tickets.entrySet().removeIf(entry -> entry.getValue().expiresAt().isBefore(now));
    }

    public record PendingBinding(
            Long userId,
            String weiboUid,
            String screenName,
            String accessToken,
            String refreshToken,
            LocalDateTime tokenExpiresAt,
            Instant expiresAt
    ) {
    }
}
