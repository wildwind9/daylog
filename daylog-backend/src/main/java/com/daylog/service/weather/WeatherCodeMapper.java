package com.daylog.service.weather;

public final class WeatherCodeMapper {

    private WeatherCodeMapper() {
    }

    public static String describe(int weatherCode) {
        return switch (weatherCode) {
            case 0 -> "\u6674";
            case 1 -> "\u5927\u90e8\u6674\u6717";
            case 2 -> "\u5c40\u90e8\u591a\u4e91";
            case 3 -> "\u9634";
            case 45, 48 -> "\u96fe";
            case 51 -> "\u5c0f\u6bdb\u6bdb\u96e8";
            case 53 -> "\u6bdb\u6bdb\u96e8";
            case 55 -> "\u5f3a\u6bdb\u6bdb\u96e8";
            case 61 -> "\u5c0f\u96e8";
            case 63 -> "\u4e2d\u96e8";
            case 65 -> "\u5927\u96e8";
            case 71 -> "\u5c0f\u96ea";
            case 73 -> "\u4e2d\u96ea";
            case 75 -> "\u5927\u96ea";
            case 80 -> "\u5c0f\u9635\u96e8";
            case 81 -> "\u9635\u96e8";
            case 82 -> "\u5f3a\u9635\u96e8";
            case 95 -> "\u96f7\u9635\u96e8";
            default -> "\u672a\u77e5\u5929\u6c14";
        };
    }
}
