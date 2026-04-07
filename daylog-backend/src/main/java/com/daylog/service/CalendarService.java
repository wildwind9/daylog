package com.daylog.service;

import com.daylog.dto.CalendarDayDto;
import com.daylog.dto.DayDetailDto;
import com.daylog.entity.ContentItem;
import com.daylog.entity.DiaryEntry;
import com.daylog.repository.*;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class CalendarService {

    private final ContentItemRepository contentItemRepository;
    private final DiaryEntryRepository diaryEntryRepository;
    private final TagRepository tagRepository;
    private final ContentTagRepository contentTagRepository;
    private final ObjectMapper objectMapper = new ObjectMapper();

    // 返回某月有内容的日期及标签气泡
    public List<CalendarDayDto> getMonthSummary(int year, int month) {
        List<LocalDate> activeDates = new ArrayList<>(new LinkedHashSet<>(
                contentItemRepository.findActiveDatesByYearAndMonth(year, month)
        ));
        diaryEntryRepository.findActiveDatesByYearAndMonth(year, month).forEach(date -> {
            if (!activeDates.contains(date)) {
                activeDates.add(date);
            }
        });
        Collections.sort(activeDates);

        return activeDates.stream().map(date -> {
            List<String> tags = tagRepository.findTagsByDate(date)
                    .stream()
                    .map(t -> t.getName())
                    .limit(3)               // 日历格最多显示 3 个气泡
                    .toList();

            int count = contentItemRepository.findByItemDateOrderByItemTimeAsc(date).size();
            DiaryEntry diary = diaryEntryRepository.findByEntryDate(date).orElse(null);
            return new CalendarDayDto(
                    date,
                    tags,
                    count,
                    diary != null ? diary.getMood() : null,
                    diary != null ? diary.getWeather() : null
            );
        }).toList();
    }

    // 返回某天的完整内容
    public DayDetailDto getDayDetail(LocalDate date) {
        List<ContentItem> items =
                contentItemRepository.findByItemDateOrderByItemTimeAsc(date);

        DiaryEntry diary = diaryEntryRepository.findByEntryDate(date).orElse(null);

        // 找 manual 类型的 body
        String diaryBody = items.stream()
                .filter(i -> i.getSource() == ContentItem.Source.manual)
                .map(ContentItem::getBody)
                .findFirst()
                .orElse(null);

        String diaryBodyFormat = items.stream()
                .filter(i -> i.getSource() == ContentItem.Source.manual)
                .map(i -> i.getBodyFormat().name())
                .findFirst()
                .orElse(null);

        // 非 manual 内容
        List<DayDetailDto.ContentItemDto> itemDtos = items.stream()
                .filter(i -> i.getSource() != ContentItem.Source.manual)
                .map(this::toDto)
                .toList();

        return DayDetailDto.builder()
                .date(date)
                .mood(diary != null ? diary.getMood() : null)
                .weather(diary != null ? diary.getWeather() : null)
                .diaryBody(diaryBody)
                .diaryBodyFormat(diaryBodyFormat)
                .items(itemDtos)
                .build();
    }

    private List<String> parseMediaJson(String json) {
        if (json == null || json.isBlank()) return Collections.emptyList();
        try {
            return objectMapper.readValue(json, new TypeReference<List<String>>() {});
        } catch (Exception e) {
            return Collections.emptyList();
        }
    }

    private DayDetailDto.ContentItemDto toDto(ContentItem item) {
        List<String> tags = contentTagRepository.findByContentItemId(item.getId())
                .stream()
                .map(ct -> ct.getTag().getName())
                .toList();

        return DayDetailDto.ContentItemDto.builder()
                .id(item.getId())
                .source(item.getSource().name())
                .contentType(item.getContentType().name())
                .title(item.getTitle())
                .body(item.getBody())
                .bodyFormat(item.getBodyFormat().name())
                .media(parseMediaJson(item.getMedia()))
                .sourceUrl(item.getSourceUrl())
                .itemTime(item.getItemTime().toString())
                .tags(tags)
                .build();
    }
}
