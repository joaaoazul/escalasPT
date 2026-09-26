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
    @Autowired
    protected TestClock clock;

    @BeforeEach
    void cleanDatabase() {
        clock.set(TestClock.DEFAULT);
        jdbc.sql("TRUNCATE users, postos, audit_events, notifications, push_subscriptions CASCADE").update();
    }

    protected Client client() {
        return new Client(mvc, json);
    }

    /** Posto com dois grupos de folgas, um comandante de grupo em cada, criado pelo administrador. */
    protected record Posto(Client admin, String postoId, String grupo1, String grupo2, Client cmd1, Client cmd2) {
    }

    protected Posto posto() {
        Client admin = militar("admin@turnos.test", "Administrador", null);
        String postoId = admin.post("/api/v1/postos", Map.of("name", "Posto Territorial de Castro Marim", "location", "Castro Marim"))
                .text("id");
        String g1 = admin.post("/api/v1/postos/" + postoId + "/groups", Map.of("name", "Grupo 1")).text("id");
        String g2 = admin.post("/api/v1/postos/" + postoId + "/groups", Map.of("name", "Grupo 2")).text("id");
        Client cmd1 = militar("matos@gnr.test", "Sofia Matos", "Cabo-Chefe");
        join(cmd1, admin.post("/api/v1/groups/" + g1 + "/invites", Map.of("role", "COMMANDER")).text("code"));
        Client cmd2 = militar("sousa@gnr.test", "Paulo Sousa", "Cabo-Chefe");
        join(cmd2, admin.post("/api/v1/groups/" + g2 + "/invites", Map.of("role", "COMMANDER")).text("code"));
        return new Posto(admin, postoId, g1, g2, cmd1, cmd2);
    }

    /** Militar convidado pelo comandante de grupo e já dentro do grupo. */
    protected Client membro(Client commander, String groupId, String email, String fullName, String rank) {
        Client c = militar(email, fullName, rank);
        join(c, commander.post("/api/v1/groups/" + groupId + "/invites", Map.of("email", email)).text("code"));
        return c;
    }

    protected static void join(Client c, String code) {
        var r = c.post("/api/v1/invites/" + code + "/accept", null);
        if (r.status() != 200) {
            throw new IllegalStateException("Aceitar convite falhou: " + r.body());
        }
    }

    /** Depois de avançar o relógio, o token de acesso expira: renova com o refresh token (como faz a app). */
    protected static void refresh(Client... clients) {
        for (Client c : clients) {
            c.post("/api/v1/auth/refresh", null);
        }
    }

    protected static String userId(Client c) {
        return c.get("/api/v1/me").text("id");
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
