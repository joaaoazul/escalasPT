package pt.turnos.support;

import java.sql.Timestamp;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.security.crypto.password.PasswordEncoder;
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
    @Autowired
    private PasswordEncoder passwords;

    protected static final String PASSWORD = "palavra-passe-segura";
    private static String passwordHash;

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
        Client admin = registar(null, "admin@turnos.test", "Administrador", null);
        String postoId = admin.post("/api/v1/postos", Map.of("name", "Posto Territorial de Castro Marim", "location", "Castro Marim"))
                .text("id");
        String g1 = admin.post("/api/v1/postos/" + postoId + "/groups", Map.of("name", "Grupo 1")).text("id");
        String g2 = admin.post("/api/v1/postos/" + postoId + "/groups", Map.of("name", "Grupo 2")).text("id");
        Client cmd1 = registar(admin.post("/api/v1/groups/" + g1 + "/invites", Map.of("role", "COMMANDER")).text("code"),
                "matos@gnr.test", "Sofia Matos", "Cabo-Chefe");
        Client cmd2 = registar(admin.post("/api/v1/groups/" + g2 + "/invites", Map.of("role", "COMMANDER")).text("code"),
                "sousa@gnr.test", "Paulo Sousa", "Cabo-Chefe");
        return new Posto(admin, postoId, g1, g2, cmd1, cmd2);
    }

    /** Militar convidado pelo comandante de grupo: cria conta com o convite e fica logo no grupo. */
    protected Client membro(Client commander, String groupId, String email, String fullName, String rank) {
        return registar(commander.post("/api/v1/groups/" + groupId + "/invites", Map.of("email", email)).text("code"), email, fullName, rank);
    }

    /** Cria conta pela API (com o código do convite, ou sem ele para o administrador) e devolve o cliente autenticado. */
    protected Client registar(String inviteCode, String email, String fullName, String rank) {
        Client c = client();
        var r = c.post("/api/v1/auth/register", registo(inviteCode, email, fullName, rank));
        if (r.status() != 201) {
            throw new IllegalStateException("Registo falhou: " + r.body());
        }
        return c;
    }

    protected static Map<String, Object> registo(String inviteCode, String email, String fullName, String rank) {
        Map<String, Object> body = new HashMap<>(Map.of("email", email, "password", PASSWORD, "fullName", fullName));
        if (rank != null) {
            body.put("rank", rank);
        }
        if (inviteCode != null) {
            body.put("inviteCode", inviteCode);
        }
        return body;
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

    /**
     * Militar com conta mas sem grupo de folgas (saiu do grupo, ou foi importado). Como o registo exige convite,
     * a conta é criada diretamente na BD; depois entra pela API como qualquer militar.
     */
    protected Client militar(String email, String fullName, String rank) {
        if (passwordHash == null) {
            passwordHash = passwords.encode(PASSWORD);
        }
        Timestamp now = Timestamp.from(clock.instant());
        jdbc.sql("""
                INSERT INTO users (id, email, password_hash, full_name, rank, system_role, created_at, updated_at)
                VALUES (:id, :e, :h, :n, :r, 'USER', :now, :now)""")
                .param("id", UUID.randomUUID()).param("e", email).param("h", passwordHash).param("n", fullName).param("r", rank)
                .param("now", now).update();
        Client c = client();
        var r = c.post("/api/v1/auth/login", Map.of("email", email, "password", PASSWORD));
        if (r.status() != 200) {
            throw new IllegalStateException("Login falhou: " + r.body());
        }
        return c;
    }
}
