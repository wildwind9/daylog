package com.daylog.scheduler;

import com.daylog.entity.SyncLog;
import com.daylog.repository.PlatformConfigRepository;
import com.daylog.repository.SyncLogRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;

@Slf4j
@Component
@RequiredArgsConstructor
public class SyncScheduler {

    private final PlatformConfigRepository platformConfigRepository;
    private final SyncLogRepository syncLogRepository;
    private final WebClient.Builder webClientBuilder;

    @Value("${daylog.python-service.base-url}")
    private String pythonServiceUrl;

    // 每 2 小时触发一次，分钟错开避免整点拥堵
    @Scheduled(cron = "0 7 */2 * * *")
    public void syncAllEnabledPlatforms() {
        platformConfigRepository.findByEnabledTrue().forEach(config -> {
            String platform = config.getPlatform();
            log.info("Starting sync for platform: {}", platform);
            try {
                // 调用 Python 微服务
                String result = webClientBuilder.build()
                        .post()
                        .uri(pythonServiceUrl + "/scrape/" + platform)
                        .retrieve()
                        .bodyToMono(String.class)
                        .block();

                log.info("Sync complete for {}: {}", platform, result);
                syncLogRepository.save(SyncLog.success(platform, 0));
            } catch (Exception e) {
                log.error("Sync failed for {}: {}", platform, e.getMessage());
                syncLogRepository.save(SyncLog.failed(platform, e.getMessage()));
            }
        });
    }
}
