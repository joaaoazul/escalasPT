package pt.turnos.support;

import java.util.HashMap;
import java.util.Map;

import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.web.servlet.MockMvc;

import tools.jackson.databind.json.JsonMapper;

@SpringBootTest(properties = "turnos.bootstrap-admin-email=admin@turnos.test")
@AutoConfigureMockMvc
@Import(TestcontainersConfig.class)
public abstract class IntegrationTest {

    @Autowired
    protected MockMvc mvc;
    @Autowired
    protected JsonMapper json;
    @Autowired
    protected JdbcClient jdbc;

    @BeforeEach
    void cleanDatabase() {
        jdbc.sql("TRUNCATE users, postos, audit_events CASCADE").update();
    }

    protected Client client() {
        return new Client(mvc, json);
    }

    /** Regista um militar e devolve o cliente já autenticado. */
    protected Client militar(String email, String fullName, String rank) {
        Client c = client();
        Map<String, Object> body = new HashMap<>(Map.of("email", email, "password", "palavra-passe-segura", "fullName", fullName));
        if (rank != null) {
            body.put("rank", rank);
        }
        var r = c.post("/api/v1/auth/register", body);
        if (r.status() != 201) {
            throw new IllegalStateException("Registo falhou: " + r.body());
        }
        return c;
    }
}
