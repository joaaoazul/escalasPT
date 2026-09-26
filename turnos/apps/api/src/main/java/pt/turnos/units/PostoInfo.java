package pt.turnos.units;

import java.time.ZoneId;
import java.util.UUID;

public record PostoInfo(UUID id, String name, String location, ZoneId zone) {
}
