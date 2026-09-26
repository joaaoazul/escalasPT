package pt.turnos.units;

import java.util.UUID;

/** A que posto e grupo de folgas pertence um militar. */
public record Membership(UUID userId, UUID postoId, UUID groupId, String groupName, boolean commander) {
}
