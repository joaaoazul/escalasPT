package pt.turnos.identity;

import java.util.UUID;

/** O militar autenticado. Pode ser pedido como parâmetro em qualquer controller. */
public record CurrentUser(UUID id, boolean admin) {
}
