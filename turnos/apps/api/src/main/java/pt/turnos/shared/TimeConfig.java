package pt.turnos.shared;

import java.time.Clock;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
class TimeConfig {

    /** Todo o código lê o tempo daqui: os testes substituem-no por um relógio fixo. */
    @Bean
    Clock clock() {
        return Clock.systemUTC();
    }
}
