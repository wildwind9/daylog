package com.daylog.service;

import com.daylog.entity.AppUser;
import com.daylog.repository.AppUserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class CurrentUserService {

    private final AppUserRepository appUserRepository;

    public AppUser currentUser() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null) {
            throw new IllegalStateException("Current user not found");
        }

        Object details = authentication.getDetails();
        if (details instanceof Long userId) {
            return appUserRepository.findById(userId)
                    .orElseThrow(() -> new IllegalStateException("Current user not found"));
        }

        String username = authentication.getName();
        return appUserRepository.findByUsernameIgnoreCase(username)
                .orElseThrow(() -> new IllegalStateException("Current user not found"));
    }

    public Long currentUserId() {
        return currentUser().getId();
    }
}
