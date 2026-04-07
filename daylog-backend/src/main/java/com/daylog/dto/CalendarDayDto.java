package com.daylog.dto;

import lombok.AllArgsConstructor;
import lombok.Getter;

import java.time.LocalDate;
import java.util.List;

@Getter
@AllArgsConstructor
public class CalendarDayDto {
    private LocalDate date;
    private List<String> tags;
    private int itemCount;
    private String mood;
    private String weather;
}
