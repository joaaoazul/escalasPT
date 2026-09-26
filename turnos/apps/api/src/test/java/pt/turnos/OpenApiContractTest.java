package pt.turnos;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

import org.junit.jupiter.api.Test;

import pt.turnos.support.IntegrationTest;
import tools.jackson.databind.SerializationFeature;
import tools.jackson.databind.json.JsonMapper;
import tools.jackson.databind.node.ObjectNode;

/**
 * contracts/openapi.json é a fonte do cliente TypeScript do frontend. Este teste falha se a API mudar
 * sem o contrato ser atualizado. Para o regravar: {@code UPDATE_CONTRACT=1 ./gradlew :apps:api:test --tests '*OpenApiContract*'}.
 */
class OpenApiContractTest extends IntegrationTest {

    private static final Path CONTRACT = Path.of("../../contracts/openapi.json");

    @Test
    void contratoEstaAtualizado() throws Exception {
        ObjectNode spec = (ObjectNode) json.readTree(client().get("/api/v3/api-docs").raw().getContentAsString());
        spec.set("servers", json.valueToTree(List.of(Map.of("url", "/"))));

        JsonMapper pretty = JsonMapper.builder()
                .enable(SerializationFeature.INDENT_OUTPUT)
                .enable(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS)
                .build();
        String current = pretty.writeValueAsString(pretty.treeToValue(spec, TreeMap.class)) + "\n";

        if (System.getenv("UPDATE_CONTRACT") != null) {
            Files.writeString(CONTRACT, current);
        }
        assertThat(Files.readString(CONTRACT))
                .as("contracts/openapi.json está desatualizado: corre o teste com UPDATE_CONTRACT=1")
                .isEqualTo(current);
    }
}
