package pt.turnos.identity.internal;

import java.time.Duration;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties("turnos.security")
record SecurityProperties(
        String jwtSecret,
        Duration accessTokenTtl,
        Duration refreshTokenTtl,
        boolean cookieSecure,
        int maxFailedLogins,
        Duration lockout) {

    String accessCookie() {
        return cookieSecure ? "__Host-turnos_at" : "turnos_at";
    }

    String refreshCookie() {
        return cookieSecure ? "__Secure-turnos_rt" : "turnos_rt";
    }
}
