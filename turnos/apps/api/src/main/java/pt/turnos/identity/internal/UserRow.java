package pt.turnos.identity.internal;

import java.time.Instant;
import java.util.UUID;

import pt.turnos.identity.UserSummary;

record UserRow(UUID id, String email, String passwordHash, String fullName, String rank, String serviceNumber,
               String systemRole, int failedLogins, Instant lockedUntil) {

    boolean admin() {
        return "ADMIN".equals(systemRole);
    }

    UserSummary summary() {
        return new UserSummary(id, email, fullName, rank, serviceNumber);
    }
}
