package pt.turnos;

import org.junit.jupiter.api.Test;
import org.springframework.modulith.core.ApplicationModules;

/** Os módulos só se usam através das APIs públicas (pacote de topo); nunca pelos pacotes internal. */
class ModularityTest {

    @Test
    void modulosRespeitamAsFronteiras() {
        ApplicationModules.of(TurnosApplication.class).verify();
    }
}
