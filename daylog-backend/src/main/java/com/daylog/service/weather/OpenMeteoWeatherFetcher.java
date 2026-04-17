package com.daylog.service.weather;

import com.fasterxml.jackson.databind.JsonNode;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

@Service
@RequiredArgsConstructor
public class OpenMeteoWeatherFetcher implements WeatherFetcher {

    private final WebClient.Builder webClientBuilder;

    @Value("${daylog.weather-service.base-url:https://api.open-meteo.com}")
    private String baseUrl;

    @Override
    public String fetchWeatherLabel(double latitude, double longitude) {
        JsonNode response = webClientBuilder.build()
                .get()
                .uri(uriBuilder -> uriBuilder
                        .scheme("https")
                        .host(stripSchemeAndPath(baseUrl))
                        .path("/v1/forecast")
                        .queryParam("latitude", latitude)
                        .queryParam("longitude", longitude)
                        .queryParam("current", "weather_code")
                        .queryParam("timezone", "auto")
                        .build())
                .retrieve()
                .bodyToMono(JsonNode.class)
                .block();

        if (response == null) {
            throw new IllegalStateException("Weather response is empty");
        }
        int weatherCode = response.path("current").path("weather_code").asInt(-1);
        if (weatherCode < 0) {
            throw new IllegalStateException("Weather code missing");
        }
        return WeatherCodeMapper.describe(weatherCode);
    }

    private String stripSchemeAndPath(String url) {
        String normalized = url == null ? "" : url.trim();
        normalized = normalized.replaceFirst("^https?://", "");
        int slashIndex = normalized.indexOf('/');
        return slashIndex >= 0 ? normalized.substring(0, slashIndex) : normalized;
    }
}
