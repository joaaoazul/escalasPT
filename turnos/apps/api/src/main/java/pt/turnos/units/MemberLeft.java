package pt.turnos.units;

import java.util.UUID;

/** Um militar saiu (ou foi removido) de um grupo de folgas e, portanto, do posto. */
public record MemberLeft(UUID userId, UUID postoId, UUID groupId, UUID actorId) {
}
