package pt.turnos.notifications;

import static org.assertj.core.api.Assertions.assertThat;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.interfaces.ECPrivateKey;
import java.security.spec.ECGenParameterSpec;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;

import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import com.sun.net.httpserver.HttpServer;

import pt.turnos.support.Client;
import pt.turnos.support.IntegrationTest;
import tools.jackson.databind.JsonNode;

class NotificationsIntegrationTest extends IntegrationTest {

    record Received(String path, String authorization, String encoding, byte[] body) {
    }

    private static final Base64.Encoder E = Base64.getUrlEncoder().withoutPadding();
    private static final LinkedBlockingQueue<Received> PUSHES = new LinkedBlockingQueue<>();
    private static HttpServer pushService;
    private static KeyPair vapid;
    private static volatile int status = 201;

    @BeforeAll
    static void startPushService() throws Exception {
        pushService = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        pushService.createContext("/", ex -> {
            PUSHES.add(new Received(ex.getRequestURI().getPath(), ex.getRequestHeaders().getFirst("Authorization"),
                    ex.getRequestHeaders().getFirst("Content-Encoding"), ex.getRequestBody().readAllBytes()));
            ex.sendResponseHeaders(status, -1);
            ex.close();
        });
        pushService.start();
    }

    @AfterAll
    static void stop() {
        pushService.stop(0);
    }

    @DynamicPropertySource
    static void vapidKeys(DynamicPropertyRegistry r) throws Exception {
        KeyPairGenerator g = KeyPairGenerator.getInstance("EC");
        g.initialize(new ECGenParameterSpec("secp256r1"));
        vapid = g.generateKeyPair();
        byte[] d = ((ECPrivateKey) vapid.getPrivate()).getS().toByteArray();
        byte[] d32 = new byte[32];
        System.arraycopy(d, Math.max(0, d.length - 32), d32, Math.max(0, 32 - d.length), Math.min(32, d.length));
        r.add("turnos.push.vapid-public-key", () -> E.encodeToString(WebPushCrypto.encodePublic(vapid)));
        r.add("turnos.push.vapid-private-key", () -> E.encodeToString(d32));
        r.add("turnos.push.allowed-hosts", () -> "fcm.googleapis.com,127.0.0.1");
    }

    private String type(Client c, String postoId, String code) {
        for (JsonNode t : c.get("/api/v1/postos/" + postoId + "/shift-types").body()) {
            if (t.path("code").asString().equals(code)) {
                return t.path("id").asString();
            }
        }
        throw new IllegalArgumentException(code);
    }

    private String paint(Client c, String postoId, String code, String date) {
        return c.put("/api/v1/me/shifts/paint", Map.of("shiftTypeId", type(c, postoId, code), "dates", List.of(date)))
                .body().path("shifts").get(0).path("id").asString();
    }

    @Test
    void pedidoDeTrocaChegaAoCamaradaNaAppEPorPush() throws Exception {
        PUSHES.clear();
        status = 201;
        Posto p = posto();
        Client ana = membro(p.cmd1(), p.grupo1(), "ana@gnr.test", "Ana Silva", "Guarda");
        Client rui = membro(p.cmd2(), p.grupo2(), "rui@gnr.test", "Rui Rocha", "Cabo");

        KeyPairGenerator g = KeyPairGenerator.getInstance("EC");
        g.initialize(new ECGenParameterSpec("secp256r1"));
        KeyPair phone = g.generateKeyPair();
        byte[] phonePublic = WebPushCrypto.encodePublic(phone);
        byte[] auth = new byte[16];
        new java.security.SecureRandom().nextBytes(auth);
        String endpoint = "http://127.0.0.1:" + pushService.getAddress().getPort() + "/push/rui";

        assertThat(rui.get("/api/v1/push/config").body().path("enabled").asBoolean()).isTrue();
        assertThat(rui.post("/api/v1/push/subscriptions", Map.of("endpoint", endpoint,
                "keys", Map.of("p256dh", E.encodeToString(phonePublic), "auth", E.encodeToString(auth)))).status()).isEqualTo(204);

        String a = paint(ana, p.postoId(), "AT2", "2026-10-07");
        String b = paint(rui, p.postoId(), "OC3", "2026-10-07");
        String id = ana.post("/api/v1/swaps", Map.of("shiftId", a, "targetShiftId", b, "message", "Tenho tribunal")).text("id");

        // In-app
        var inbox = rui.get("/api/v1/notifications").body();
        assertThat(inbox.path("unread").asInt()).isEqualTo(1);
        assertThat(inbox.path("items").get(0).path("title").asString()).isEqualTo("Pedido de troca");
        assertThat(inbox.path("items").get(0).path("body").asString())
                .isEqualTo("Guarda Ana Silva quer trocar o teu OC3 de 07/10 pelo AT2. “Tenho tribunal”");

        // Push: cifrado para o telemóvel do Rui e assinado com VAPID
        Received push = PUSHES.poll(10, TimeUnit.SECONDS);
        assertThat(push).isNotNull();
        assertThat(push.path()).isEqualTo("/push/rui");
        assertThat(push.encoding()).isEqualTo("aes128gcm");
        assertThat(push.authorization()).startsWith("vapid t=");
        String json = new String(WebPushCrypto.decrypt(push.body(), phone.getPrivate(), phonePublic, auth), StandardCharsets.UTF_8);
        assertThat(json).contains("\"title\":\"Pedido de troca\"").contains("\"url\":\"/grupo?s=trocas\"");

        assertThat(rui.post("/api/v1/notifications/read", null).body().path("updated").asInt()).isEqualTo(1);
        assertThat(rui.get("/api/v1/notifications").body().path("unread").asInt()).isZero();

        // Resposta chega a quem pediu
        rui.post("/api/v1/swaps/" + id + "/accept", null);
        var anaInbox = ana.get("/api/v1/notifications").body();
        assertThat(anaInbox.path("items").get(0).path("title").asString()).isEqualTo("Troca aceite");
    }

    @Test
    void subscricaoRemovidaQuandoOServicoDizQueExpirou() throws Exception {
        PUSHES.clear();
        status = 410;
        Posto p = posto();
        Client ana = membro(p.cmd1(), p.grupo1(), "ana@gnr.test", "Ana Silva", "Guarda");
        Client rui = membro(p.cmd2(), p.grupo2(), "rui@gnr.test", "Rui Rocha", "Cabo");
        KeyPairGenerator g = KeyPairGenerator.getInstance("EC");
        g.initialize(new ECGenParameterSpec("secp256r1"));
        byte[] pub = WebPushCrypto.encodePublic(g.generateKeyPair());
        rui.post("/api/v1/push/subscriptions", Map.of("endpoint", "http://127.0.0.1:" + pushService.getAddress().getPort() + "/gone",
                "keys", Map.of("p256dh", E.encodeToString(pub), "auth", E.encodeToString(new byte[16]))));

        ana.post("/api/v1/swaps", Map.of("shiftId", paint(ana, p.postoId(), "AT2", "2026-10-07"),
                "targetShiftId", paint(rui, p.postoId(), "OC3", "2026-10-07")));
        assertThat(PUSHES.poll(10, TimeUnit.SECONDS)).isNotNull();
        for (int i = 0; i < 50 && count() > 0; i++) {
            Thread.sleep(100);
        }
        assertThat(count()).isZero();
        status = 201;
    }

    @Test
    void endpointsForaDosServicosDePushSaoRecusados() {
        Client ana = militar("ana@gnr.test", "Ana Silva", "Guarda");
        var r = ana.post("/api/v1/push/subscriptions", Map.of("endpoint", "https://169.254.169.254/latest/meta-data",
                "keys", Map.of("p256dh", "x", "auth", "y")));
        assertThat(r.status()).isEqualTo(422);
        assertThat(r.text("code")).isEqualTo("push-endpoint-not-allowed");
    }

    private long count() {
        return jdbc.sql("SELECT count(*) FROM push_subscriptions").query(Long.class).single();
    }
}
