package pt.turnos.identity;

import java.util.UUID;

/** Dados de identificação de um militar, como aparecem na escala e no documento de troca. */
public record UserSummary(UUID id, String email, String fullName, String rank, String serviceNumber) {

    /** "Guarda Ana Silva", tal como no campo {@code full_name} do EscalasPT. */
    public String displayName() {
        return rank == null || rank.isBlank() ? fullName : rank + " " + fullName;
    }
}
