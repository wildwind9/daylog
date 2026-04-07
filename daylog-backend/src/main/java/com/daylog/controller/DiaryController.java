package com.daylog.controller;

import com.daylog.dto.ApiResponse;
import com.daylog.entity.ContentItem;
import com.daylog.entity.DiaryEntry;
import com.daylog.repository.ContentItemRepository;
import com.daylog.repository.DiaryEntryRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import lombok.Setter;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.time.LocalDateTime;

@RestController
@RequestMapping("/api/diary")
@RequiredArgsConstructor
@Tag(name = "Diary", description = "手动日记接口")
@SecurityRequirement(name = "bearerAuth")
public class DiaryController {

    private final DiaryEntryRepository diaryEntryRepository;
    private final ContentItemRepository contentItemRepository;

    @PutMapping("/{date}")
    @Operation(summary = "新增或更新某天日记")
    @Transactional
    public ApiResponse<Void> upsertDiary(
            @PathVariable @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date,
            @Valid @RequestBody DiaryRequest request) {

        // 更新情绪天气
        DiaryEntry entry = diaryEntryRepository.findByEntryDate(date)
                .orElseGet(() -> {
                    DiaryEntry e = new DiaryEntry();
                    e.setEntryDate(date);
                    return e;
                });
        entry.setMood(request.getMood());
        entry.setWeather(request.getWeather());
        entry.setUpdatedAt(LocalDateTime.now());
        diaryEntryRepository.save(entry);

        // 更新 manual content_item（富文本 body）
        contentItemRepository.findByItemDateOrderByItemTimeAsc(date)
                .stream()
                .filter(i -> i.getSource() == ContentItem.Source.manual)
                .findFirst()
                .ifPresentOrElse(item -> {
                    item.setBody(request.getBody());
                    item.setBodyFormat(ContentItem.BodyFormat.valueOf(
                            request.getBodyFormat() != null ? request.getBodyFormat() : "tiptap_json"));
                    contentItemRepository.save(item);
                }, () -> {
                    ContentItem item = new ContentItem();
                    item.setSource(ContentItem.Source.manual);
                    item.setContentType(ContentItem.ContentType.rich_text);
                    item.setBody(request.getBody());
                    item.setBodyFormat(ContentItem.BodyFormat.valueOf(
                            request.getBodyFormat() != null ? request.getBodyFormat() : "tiptap_json"));
                    item.setItemDate(date);
                    item.setItemTime(date.atStartOfDay());
                    contentItemRepository.save(item);
                });

        return ApiResponse.ok(null);
    }

    @Getter @Setter
    public static class DiaryRequest {
        private String body;
        private String bodyFormat;   // tiptap_json / html / plain
        private String mood;
        private String weather;
    }
}
