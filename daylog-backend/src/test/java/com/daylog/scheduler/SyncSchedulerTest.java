package com.daylog.scheduler;

import com.daylog.entity.PlatformConfig;
import com.daylog.entity.SyncLog;
import com.daylog.entity.WeiboBinding;
import com.daylog.repository.PlatformConfigRepository;
import com.daylog.repository.SyncLogRepository;
import com.daylog.repository.WeiboBindingRepository;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTimeoutPreemptively;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class SyncSchedulerTest {

    /**
     * Regression for 2026-09-21: the Python scrape never responded, block() waited forever
     * and the single scheduling thread stopped every @Scheduled job.
     */
    @Test
    void hanging_python_call_times_out_and_next_platform_still_runs() {
        PlatformConfigRepository platformConfigRepository = mock(PlatformConfigRepository.class);
        SyncLogRepository syncLogRepository = mock(SyncLogRepository.class);
        WeiboBindingRepository weiboBindingRepository = mock(WeiboBindingRepository.class);

        PlatformConfig hanging = config(1L, "weibo");
        PlatformConfig healthy = config(5L, "weibo");
        when(platformConfigRepository.findByEnabledTrue()).thenReturn(List.of(hanging, healthy));
        when(weiboBindingRepository.findByUserIdAndActiveTrue(1L)).thenReturn(Optional.of(binding(3L)));
        when(weiboBindingRepository.findByUserIdAndActiveTrue(5L)).thenReturn(Optional.of(binding(4L)));

        WebClient.Builder builder = WebClient.builder().exchangeFunction(request -> {
            if (request.url().getQuery().contains("userId=1")) {
                return Mono.never();
            }
            return Mono.just(ClientResponse.create(HttpStatus.OK)
                    .header(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                    .body("{\"status\":\"success\"}")
                    .build());
        });

        SyncScheduler scheduler = new SyncScheduler(
                platformConfigRepository, syncLogRepository, weiboBindingRepository, builder);
        ReflectionTestUtils.setField(scheduler, "pythonServiceUrl", "http://python.test");
        ReflectionTestUtils.setField(scheduler, "scrapeTimeout", Duration.ofMillis(200));

        assertTimeoutPreemptively(Duration.ofSeconds(5), scheduler::syncAllEnabledPlatforms);

        ArgumentCaptor<SyncLog> logs = ArgumentCaptor.forClass(SyncLog.class);
        verify(syncLogRepository, times(2)).save(logs.capture());
        assertEquals(1L, logs.getAllValues().get(0).getUserId());
        assertEquals("failed", logs.getAllValues().get(0).getStatus());
        assertEquals(5L, logs.getAllValues().get(1).getUserId());
        assertEquals("success", logs.getAllValues().get(1).getStatus());
    }

    private static PlatformConfig config(Long userId, String platform) {
        PlatformConfig config = new PlatformConfig();
        config.setUserId(userId);
        config.setPlatform(platform);
        config.setEnabled(true);
        return config;
    }

    private static WeiboBinding binding(Long id) {
        WeiboBinding binding = new WeiboBinding();
        binding.setId(id);
        return binding;
    }
}
