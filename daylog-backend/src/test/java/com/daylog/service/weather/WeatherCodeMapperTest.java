package com.daylog.service.weather;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class WeatherCodeMapperTest {

    @Test
    void describes_common_weather_codes() {
        assertEquals("\u6674", WeatherCodeMapper.describe(0));
        assertEquals("\u6652", WeatherCodeMapper.describe(2));
        assertEquals("\u5c0f\u96e8", WeatherCodeMapper.describe(61));
        assertEquals("\u96f7\u9635\u96e8", WeatherCodeMapper.describe(95));
        assertEquals("\u672a\u77e5\u5929\u6c14", WeatherCodeMapper.describe(999));
    }
}
