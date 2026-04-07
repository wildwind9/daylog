package com.daylog.dto;

import com.daylog.entity.ContentItem;
import com.daylog.entity.DiaryEntry;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDate;
import java.util.List;

@Getter
@Builder
public class DayDetailDto {
    private LocalDate date;
    private String mood;
    private String weather;
    private String diaryBody;       // 手动日记富文本内容
    private String diaryBodyFormat;
    private List<ContentItemDto> items;

    @Getter
    @Builder
    public static class ContentItemDto {
        private Long id;
        private String source;
        private String contentType;
        private String title;
        private String body;
        private String bodyFormat;
        private List<String> media;
        private String sourceUrl;
        private String itemTime;
        private List<String> tags;
    }
}
