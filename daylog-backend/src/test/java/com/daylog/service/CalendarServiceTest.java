package com.daylog.service;

import com.daylog.dto.CalendarSearchResultDto;
import com.daylog.entity.ContentItem;
import com.daylog.entity.ContentTag;
import com.daylog.entity.DiaryEntry;
import com.daylog.entity.Tag;
import com.daylog.repository.ContentItemRepository;
import com.daylog.repository.ContentTagRepository;
import com.daylog.repository.DiaryEntryRepository;
import com.daylog.repository.TagRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CalendarServiceTest {

    @Mock
    private ContentItemRepository contentItemRepository;

    @Mock
    private DiaryEntryRepository diaryEntryRepository;

    @Mock
    private TagRepository tagRepository;

    @Mock
    private ContentTagRepository contentTagRepository;

    @InjectMocks
    private CalendarService calendarService;

    @Test
    void searchAllContentFindsBodyTagsAndDiaryMetadata() {
        Long userId = 7L;
        ContentItem bodyMatch = contentItem(10L, userId, LocalDate.of(2026, 4, 6), "morning-run", "today ran by the lake");
        ContentItem tagMatch = contentItem(11L, userId, LocalDate.of(2026, 4, 7), "lunch", "plain note");
        DiaryEntry weatherMatch = diaryEntry(userId, LocalDate.of(2026, 4, 8), "calm", "light-rain");
        Tag sportTag = tag(21L, "exercise");

        when(contentItemRepository.searchByUserIdAndQuery(eq(userId), eq("run"))).thenReturn(List.of(bodyMatch));
        when(contentItemRepository.searchByUserIdAndTagName(eq(userId), eq("run"))).thenReturn(List.of(tagMatch));
        when(diaryEntryRepository.searchByUserIdAndQuery(eq(userId), eq("run"))).thenReturn(List.of(weatherMatch));
        when(contentTagRepository.findByContentItemId(10L)).thenReturn(List.of());
        when(contentTagRepository.findByContentItemId(11L)).thenReturn(List.of(contentTag(tagMatch, sportTag)));
        when(diaryEntryRepository.findByUserIdAndEntryDate(userId, LocalDate.of(2026, 4, 6))).thenReturn(Optional.empty());
        when(diaryEntryRepository.findByUserIdAndEntryDate(userId, LocalDate.of(2026, 4, 7))).thenReturn(Optional.empty());
        when(tagRepository.findTagsByUserIdAndDate(userId, LocalDate.of(2026, 4, 8))).thenReturn(List.of());

        List<CalendarSearchResultDto> results = calendarService.searchAllContent(userId, "  run ");

        assertThat(results).extracting(CalendarSearchResultDto::getDate)
                .containsExactly(
                        LocalDate.of(2026, 4, 8),
                        LocalDate.of(2026, 4, 7),
                        LocalDate.of(2026, 4, 6)
                );
        assertThat(results.get(0).getMatchedText()).isEqualTo("calm light-rain");
        assertThat(results.get(1).getTags()).containsExactly("exercise");
        assertThat(results.get(2).getMatchedText()).contains("lake");
    }

    @Test
    void searchAllContentReturnsEmptyListForBlankQuery() {
        assertThat(calendarService.searchAllContent(7L, "   ")).isEmpty();
    }

    private static ContentItem contentItem(Long id, Long userId, LocalDate date, String title, String body) {
        ContentItem item = new ContentItem();
        item.setId(id);
        item.setUserId(userId);
        item.setItemDate(date);
        item.setItemTime(LocalDateTime.of(date.getYear(), date.getMonth(), date.getDayOfMonth(), 12, 0));
        item.setSource(ContentItem.Source.manual);
        item.setContentType(ContentItem.ContentType.text);
        item.setBodyFormat(ContentItem.BodyFormat.plain);
        item.setTitle(title);
        item.setBody(body);
        return item;
    }

    private static DiaryEntry diaryEntry(Long userId, LocalDate date, String mood, String weather) {
        DiaryEntry entry = new DiaryEntry();
        entry.setUserId(userId);
        entry.setEntryDate(date);
        entry.setMood(mood);
        entry.setWeather(weather);
        return entry;
    }

    private static Tag tag(Long id, String name) {
        Tag tag = new Tag();
        tag.setId(id);
        tag.setName(name);
        return tag;
    }

    private static ContentTag contentTag(ContentItem item, Tag tag) {
        return new ContentTag(item, tag, ContentTag.TagSource.manual);
    }
}
