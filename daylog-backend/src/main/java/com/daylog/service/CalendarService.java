package com.daylog.service;

import com.daylog.dto.CalendarDayDto;
import com.daylog.dto.CalendarSearchResultDto;
import com.daylog.dto.DayDetailDto;
import com.daylog.entity.ContentItem;
import com.daylog.entity.DiaryEntry;
import com.daylog.repository.ContentItemRepository;
import com.daylog.repository.ContentTagRepository;
import com.daylog.repository.DiaryEntryRepository;
import com.daylog.repository.TagRepository;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class CalendarService {

    private final ContentItemRepository contentItemRepository;
    private final DiaryEntryRepository diaryEntryRepository;
    private final TagRepository tagRepository;
    private final ContentTagRepository contentTagRepository;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public List<CalendarDayDto> getMonthSummary(Long userId, int year, int month) {
        List<LocalDate> activeDates = new ArrayList<>(new LinkedHashSet<>(
                contentItemRepository.findActiveDatesByUserIdAndYearAndMonth(userId, year, month)
        ));
        diaryEntryRepository.findActiveDatesByUserIdAndYearAndMonth(userId, year, month).forEach(date -> {
            if (!activeDates.contains(date)) {
                activeDates.add(date);
            }
        });
        Collections.sort(activeDates);

        return activeDates.stream().map(date -> {
            List<String> tags = tagRepository.findTagsByUserIdAndDate(userId, date)
                    .stream()
                    .map(tag -> tag.getName())
                    .limit(3)
                    .toList();

            int count = contentItemRepository.findByUserIdAndItemDateOrderByItemTimeAsc(userId, date).size();
            DiaryEntry diary = diaryEntryRepository.findByUserIdAndEntryDate(userId, date).orElse(null);
            return new CalendarDayDto(
                    date,
                    tags,
                    count,
                    diary != null ? diary.getMood() : null,
                    diary != null ? diary.getWeather() : null
            );
        }).toList();
    }

    public DayDetailDto getDayDetail(Long userId, LocalDate date) {
        List<ContentItem> items =
                contentItemRepository.findByUserIdAndItemDateOrderByItemTimeAsc(userId, date);

        DiaryEntry diary = diaryEntryRepository.findByUserIdAndEntryDate(userId, date).orElse(null);

        String diaryBody = items.stream()
                .filter(item -> item.getSource() == ContentItem.Source.manual)
                .map(ContentItem::getBody)
                .findFirst()
                .orElse(null);

        String diaryBodyFormat = items.stream()
                .filter(item -> item.getSource() == ContentItem.Source.manual)
                .map(item -> item.getBodyFormat().name())
                .findFirst()
                .orElse(null);

        List<DayDetailDto.ContentItemDto> itemDtos = items.stream()
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

    public List<CalendarSearchResultDto> searchAllContent(Long userId, String query) {
        String normalizedQuery = query == null ? "" : query.trim();
        if (normalizedQuery.isBlank()) return Collections.emptyList();
        if (normalizedQuery.length() > 100) {
            normalizedQuery = normalizedQuery.substring(0, 100);
        }
        String searchQuery = normalizedQuery;

        List<CalendarSearchResultDto> results = new ArrayList<>();
        Set<Long> seenItemIds = new HashSet<>();

        contentItemRepository.searchByUserIdAndQuery(userId, searchQuery)
                .forEach(item -> addContentSearchResult(results, seenItemIds, item, searchQuery));
        contentItemRepository.searchByUserIdAndTagName(userId, searchQuery)
                .forEach(item -> addContentSearchResult(results, seenItemIds, item, searchQuery));
        diaryEntryRepository.searchByUserIdAndQuery(userId, searchQuery)
                .forEach(entry -> results.add(toDiarySearchResult(userId, entry)));

        return results.stream()
                .sorted(Comparator.comparing(CalendarSearchResultDto::getDate).reversed())
                .limit(50)
                .toList();
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
                .map(contentTag -> contentTag.getTag().getName())
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

    private void addContentSearchResult(
            List<CalendarSearchResultDto> results,
            Set<Long> seenItemIds,
            ContentItem item,
            String query) {
        if (!seenItemIds.add(item.getId())) return;

        DiaryEntry diary = diaryEntryRepository.findByUserIdAndEntryDate(item.getUserId(), item.getItemDate())
                .orElse(null);
        List<String> tags = contentTagRepository.findByContentItemId(item.getId())
                .stream()
                .map(contentTag -> contentTag.getTag().getName())
                .toList();

        results.add(new CalendarSearchResultDto(
                item.getItemDate(),
                item.getTitle(),
                pickMatchedText(item, tags, query),
                item.getSource().name(),
                diary != null ? diary.getMood() : null,
                diary != null ? diary.getWeather() : null,
                tags
        ));
    }

    private CalendarSearchResultDto toDiarySearchResult(Long userId, DiaryEntry entry) {
        List<String> tags = tagRepository.findTagsByUserIdAndDate(userId, entry.getEntryDate())
                .stream()
                .map(tag -> tag.getName())
                .toList();
        String matchedText = joinNonBlank(entry.getMood(), entry.getWeather());

        return new CalendarSearchResultDto(
                entry.getEntryDate(),
                "日记信息",
                matchedText,
                "diary",
                entry.getMood(),
                entry.getWeather(),
                tags
        );
    }

    private String pickMatchedText(ContentItem item, List<String> tags, String query) {
        String lowerQuery = query.toLowerCase(Locale.ROOT);
        if (containsIgnoreCase(item.getTitle(), lowerQuery)) return snippet(item.getTitle());
        if (containsIgnoreCase(item.getBody(), lowerQuery)) return snippet(item.getBody());

        String tagMatch = tags.stream()
                .filter(tag -> containsIgnoreCase(tag, lowerQuery))
                .findFirst()
                .orElse(null);
        if (tagMatch != null) return tagMatch;

        return snippet(joinNonBlank(item.getTitle(), item.getBody()));
    }

    private boolean containsIgnoreCase(String value, String lowerQuery) {
        return value != null && value.toLowerCase(Locale.ROOT).contains(lowerQuery);
    }

    private String snippet(String value) {
        if (value == null) return "";
        String compact = value.replaceAll("\\s+", " ").trim();
        return compact.length() > 140 ? compact.substring(0, 140) + "..." : compact;
    }

    private String joinNonBlank(String... values) {
        return Arrays.stream(values)
                .filter(value -> value != null && !value.isBlank())
                .reduce((left, right) -> left + " " + right)
                .orElse("");
    }
}
