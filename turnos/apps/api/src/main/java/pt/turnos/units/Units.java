package pt.turnos.units;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

/** API pública do módulo units. */
public interface Units {

    Optional<Membership> membershipOf(UUID userId);

    Optional<PostoInfo> posto(UUID postoId);

    /** Todos os militares do posto (de todos os grupos de folgas). */
    List<Membership> membersOfPosto(UUID postoId);
}
