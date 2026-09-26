package pt.turnos.identity;

import java.util.UUID;

/**
 * Só se cria conta com um convite de grupo de folgas (exceto o administrador de arranque). O módulo units
 * implementa esta interface; o identity chama-a no registo, dentro da mesma transação.
 */
public interface RegistrationInvites {

    /** Confirma que o convite serve para este email, antes de criar a conta. Lança {@code ApiException} se não servir. */
    void check(String code, String email);

    /** Junta ao grupo do convite o militar acabado de registar. */
    void redeem(String code, UUID userId);
}
