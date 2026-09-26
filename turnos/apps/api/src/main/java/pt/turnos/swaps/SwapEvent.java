package pt.turnos.swaps;

import java.time.LocalDate;
import java.util.UUID;

/** Publicado em cada mudança de estado de um pedido de troca (consumido pelas notificações). */
public record SwapEvent(Type type, UUID swapId, UUID requesterId, UUID targetId, LocalDate date,
                        String requesterShiftCode, String targetShiftCode, String note) {

    public enum Type { REQUESTED, HELD, ACCEPTED, DECLINED, CANCELLED, EXPIRED }
}
