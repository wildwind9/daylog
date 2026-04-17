package com.daylog.controller;

import com.daylog.dto.ApiResponse;
import com.daylog.dto.CalendarDayDto;
import com.daylog.dto.CalendarSearchResultDto;
import com.daylog.dto.DayDetailDto;
import com.daylog.service.CalendarService;
import com.daylog.service.CurrentUserService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.time.YearMonth;
import java.util.List;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
@Tag(name = "Calendar", description = "日历与日详情接口")
public class CalendarController {

    private final CalendarService calendarService;
    private final CurrentUserService currentUserService;

    @GetMapping("/calendar")
    @Operation(summary = "获取某月日历摘要", description = "返回有内容的日期及标签气泡")
    public ApiResponse<List<CalendarDayDto>> getMonthSummary(
            @RequestParam(name = "year", defaultValue = "#{T(java.time.Year).now().getValue()}") int year,
            @RequestParam(name = "month", defaultValue = "#{T(java.time.MonthDay).now().getMonthValue()}") int month) {

        // 默认返回当前年月
        if (year == 0) year = YearMonth.now().getYear();
        if (month == 0) month = YearMonth.now().getMonthValue();

        return ApiResponse.ok(calendarService.getMonthSummary(currentUserService.currentUserId(), year, month));
    }

    @GetMapping("/day/{date}")
    @Operation(summary = "获取某天详情", description = "返回当天所有内容、手动日记、情绪天气")
    public ApiResponse<DayDetailDto> getDayDetail(
            @PathVariable("date") @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date) {
        return ApiResponse.ok(calendarService.getDayDetail(currentUserService.currentUserId(), date));
    }

    @GetMapping("/search")
    @Operation(summary = "搜索所有内容", description = "按关键词模糊搜索内容、标签、心情和天气")
    public ApiResponse<List<CalendarSearchResultDto>> searchAllContent(@RequestParam("q") String q) {
        return ApiResponse.ok(calendarService.searchAllContent(currentUserService.currentUserId(), q));
    }
}
