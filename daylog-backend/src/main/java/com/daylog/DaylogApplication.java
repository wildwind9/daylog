package com.daylog;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class DaylogApplication {
    public static void main(String[] args) {
        SpringApplication.run(DaylogApplication.class, args);
    }
}
