package com.daylog.scheduler;

import com.daylog.entity.SyncLog;
import com.daylog.entity.WeiboBinding;
import com.daylog.repository.PlatformConfigRepository;
import com.daylog.repository.SyncLogRepository;
import com.daylog.repository.WeiboBindingRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;

@Slf4j
@Component
@RequiredArgsConstructor
public class SyncScheduler {

    private final PlatformConfigRepository platformConfigRepository;
    private final SyncLogRepository syncLogRepository;
    private final WeiboBindingRepository weiboBindingRepository;
    private final WebClient.Builder webClientBuilder;

    @Value("${daylog.python-service.base-url}")
    private String pythonServiceUrl;

    /** Must exceed the Python-side SCRAPE_TIMEOUT_SECONDS (900s) so Python can report its own timeout first. */
    @Value("${daylog.python-service.scrape-timeout:PT20M}")
    private Duration scrapeTimeout;

    @Scheduled(cron = "0 0 4 * * *", zone = "Asia/Shanghai")
    public void syncAllEnabledPlatforms() {
        platformConfigRepository.findByEnabledTrue().forEach(config -> {
            String platform = config.getPlatform();
            log.info("Starting sync for platform: {}", platform);
            try {
                String path = pythonServiceUrl + "/scrape/" + platform + "?userId=" + config.getUserId();
                if ("weibo".equals(platform)) {
                    WeiboBinding binding = weiboBindingRepository.findByUserIdAndActiveTrue(config.getUserId())
                            .orElseThrow(() -> new IllegalStateException("No active Weibo binding"));
                    path += "&bindingId=" + binding.getId();
                }
                String result = webClientBuilder.build()
                        .post()
                        .uri(path)
                        .retrieve()
                        .bodyToMono(String.class)
                        .block(scrapeTimeout);

                log.info("Sync complete for {}: {}", platform, result);
                syncLogRepository.save(SyncLog.success(config.getUserId(), platform, 0));
            } catch (Exception e) {
                log.error("Sync failed for {}: {}", platform, e.getMessage());
                syncLogRepository.save(SyncLog.failed(config.getUserId(), platform, e.getMessage()));
            }
        });
    }
}
