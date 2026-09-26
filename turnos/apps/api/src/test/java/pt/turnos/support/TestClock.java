package pt.turnos.support;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;

/** Relógio controlável: os testes fixam "hoje" e avançam o tempo (expiração na véspera, etc.). */
public class TestClock extends Clock {

    public static final Instant DEFAULT = Instant.parse("2026-09-26T10:00:00Z");

    private volatile Instant now = DEFAULT;

    public void set(Instant instant) {
        now = instant;
    }

    public void advance(Duration d) {
        now = now.plus(d);
    }

    @Override
    public ZoneId getZone() {
        return ZoneOffset.UTC;
    }

    @Override
    public Clock withZone(ZoneId zone) {
        TestClock outer = this;
        return new Clock() {
            @Override
            public ZoneId getZone() {
                return zone;
            }

            @Override
            public Clock withZone(ZoneId z) {
                return outer.withZone(z);
            }

            @Override
            public Instant instant() {
                return outer.instant();
            }
        };
    }

    @Override
    public Instant instant() {
        return now;
    }
}
