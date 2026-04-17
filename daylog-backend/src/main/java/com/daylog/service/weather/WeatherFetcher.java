package com.daylog.service.weather;

public interface WeatherFetcher {
    String fetchWeatherLabel(double latitude, double longitude);
}
