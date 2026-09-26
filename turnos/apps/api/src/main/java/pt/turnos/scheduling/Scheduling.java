package pt.turnos.scheduling;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/** API pública do módulo scheduling (usada pelas trocas). */
public interface Scheduling {

    Optional<ShiftInfo> find(UUID shiftId);

    /** Bloqueia os serviços (SELECT … FOR UPDATE) por ordem de id, para não haver deadlocks entre trocas. */
    List<ShiftInfo> lockForUpdate(List<UUID> shiftIds);

    List<ShiftInfo> ofUser(UUID userId, LocalDate from, LocalDate toInclusive);

    /** Troca os donos de dois serviços na transação atual (as constraints de sobreposição são diferidas até ao commit). */
    void swapOwners(ShiftInfo a, ShiftInfo b, UUID swapRequestId);
}
