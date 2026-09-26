package pt.turnos.identity;

import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/** API pública do módulo identity para os outros módulos. */
public interface UserDirectory {

    Optional<UserSummary> find(UUID id);

    List<UserSummary> findAll(Collection<UUID> ids);
}
