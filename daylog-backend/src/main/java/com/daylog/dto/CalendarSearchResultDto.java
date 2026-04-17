package com.daylog.dto;

import lombok.AllArgsConstructor;
import lombok.Getter;

import java.time.LocalDate;
import java.util.List;

@Getter
@AllArgsConstructor
public class CalendarSearchResultDto {
    private LocalDate date;
    private String title;
    private String matchedText;
    private String source;
    private String mood;
    private String weather;
    private List<String> tags;
}
