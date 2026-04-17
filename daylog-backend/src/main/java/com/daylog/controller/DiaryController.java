package com.daylog.controller;

import com.daylog.dto.ApiResponse;
import com.daylog.entity.ContentItem;
import com.daylog.entity.DiaryEntry;
import com.daylog.repository.ContentItemRepository;
import com.daylog.repository.DiaryEntryRepository;
import com.daylog.service.CurrentUserService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import lombok.Setter;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.time.LocalDateTime;

@RestController
@RequestMapping("/api/diary")
@RequiredArgsConstructor
@Tag(name = "Diary", description = "Manual diary API")
@SecurityRequirement(name = "bearerAuth")
public class DiaryController {

    private final DiaryEntryRepository diaryEntryRepository;
    private final ContentItemRepository contentItemRepository;
    private final CurrentUserService currentUserService;

    @PutMapping("/{date}")
    @Operation(summary = "Update day metadata and append a manual diary entry")
    @Transactional
    public ApiResponse<Void> upsertDiary(
            @PathVariable("date") @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date,
            @Valid @RequestBody DiaryRequest request) {

        Long userId = currentUserService.currentUserId();
        DiaryEntry entry = diaryEntryRepository.findByUserIdAndEntryDate(userId, date)
                .orElseGet(() -> {
                    DiaryEntry e = new DiaryEntry();
                    e.setEntryDate(date);
                    e.setUserId(userId);
                    return e;
                });
        entry.setMood(request.getMood());
        entry.setWeather(request.getWeather());
        entry.setUpdatedAt(LocalDateTime.now());
        diaryEntryRepository.save(entry);

        if (request.getBody() != null && !request.getBody().isBlank()) {
            LocalDateTime now = LocalDateTime.now();
            ContentItem item = new ContentItem();
            item.setSource(ContentItem.Source.manual);
            item.setContentType(ContentItem.ContentType.rich_text);
            item.setBody(request.getBody());
            item.setBodyFormat(ContentItem.BodyFormat.valueOf(
                    request.getBodyFormat() != null ? request.getBodyFormat() : "tiptap_json"));
            item.setItemDate(date);
            item.setItemTime(now);
            item.setUserId(userId);
            contentItemRepository.save(item);
        }

        return ApiResponse.ok(null);
    }

    @DeleteMapping("/{date}/{itemId}")
    @Operation(summary = "Delete a manual diary entry")
    @Transactional
    public ApiResponse<Void> deleteDiaryEntry(
            @PathVariable("date") @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date,
            @PathVariable("itemId") Long itemId) {

        return contentItemRepository.findById(itemId)
                .filter(item -> item.getUserId().equals(currentUserService.currentUserId()))
                .filter(item -> item.getSource() == ContentItem.Source.manual)
                .filter(item -> item.getItemDate().equals(date))
                .map(item -> {
                    contentItemRepository.delete(item);
                    return ApiResponse.<Void>ok(null);
                })
                .orElseGet(() -> ApiResponse.fail("Diary entry not found"));
    }

    @Getter
    @Setter
    public static class DiaryRequest {
        private String body;
        private String bodyFormat;
        private String mood;
        private String weather;
    }
}
