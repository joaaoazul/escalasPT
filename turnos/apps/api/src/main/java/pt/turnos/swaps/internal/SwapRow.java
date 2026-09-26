package pt.turnos.swaps.internal;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

record SwapRow(UUID id, UUID postoId, UUID requesterId, UUID requesterShiftId, int requesterShiftVersion, UUID targetId,
               UUID targetShiftId, int targetShiftVersion, String status, String message, String holdMessage,
               String declineReason, Instant heldAt, Instant respondedAt, Instant expiresAt, Instant createdAt, int version) {

    static final List<String> ACTIVE = List.of("PENDENTE", "EM_ESPERA");

    boolean active() {
        return ACTIVE.contains(status);
    }

    boolean involves(UUID userId) {
        return requesterId.equals(userId) || targetId.equals(userId);
    }
}
