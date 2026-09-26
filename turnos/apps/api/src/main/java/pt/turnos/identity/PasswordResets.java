package pt.turnos.identity;

import java.time.Instant;
import java.util.UUID;

/** Códigos de reposição de palavra-passe, emitidos por quem tem autoridade sobre o militar (verificada por quem chama). */
public interface PasswordResets {

    record Issued(String code, Instant expiresAt) {
    }

    /** Novo código de uso único; os anteriores ainda por usar deixam de valer. */
    Issued issue(UUID userId, UUID issuedBy);
}
