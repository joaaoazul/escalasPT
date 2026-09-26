package pt.turnos.identity;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Map;

import org.junit.jupiter.api.Test;

import jakarta.servlet.http.Cookie;
import pt.turnos.support.Client;
import pt.turnos.support.IntegrationTest;

class AuthIntegrationTest extends IntegrationTest {

    private static final String RT = "__Secure-turnos_rt";
    private static final String AT = "__Host-turnos_at";

    @Test
    void registoAbreSessaoComCookiesHttpOnly() {
        Client c = militar("ana.silva@gnr.test", "Ana Silva", "Guarda");

        assertThat(c.cookies()).containsKeys(AT, RT);
        var me = c.get("/api/v1/me");
        assertThat(me.status()).isEqualTo(200);
        assertThat(me.text("fullName")).isEqualTo("Ana Silva");
        assertThat(me.body().path("admin").asBoolean()).isFalse();
    }

    @Test
    void emailDeBootstrapFicaAdmin() {
        Client admin = militar("admin@turnos.test", "Administrador", null);
        assertThat(admin.get("/api/v1/me").body().path("admin").asBoolean()).isTrue();
    }

    @Test
    void semSessaoDa401() {
        assertThat(client().get("/api/v1/me").status()).isEqualTo(401);
    }

    @Test
    void metodosQueAlteramEstadoExigemCabecalhoDoCliente() {
        var r = client().withoutClientHeader().post("/api/v1/auth/login", Map.of("email", "x@y.pt", "password", "z"));
        assertThat(r.status()).isEqualTo(403);
        assertThat(r.text("code")).isEqualTo("client-header");
    }

    @Test
    void emailDuplicadoDa409() {
        militar("ana.silva@gnr.test", "Ana Silva", "Guarda");
        var r = client().post("/api/v1/auth/register", Map.of(
                "email", "ANA.SILVA@gnr.test", "password", "palavra-passe-segura", "fullName", "Outra"));
        assertThat(r.status()).isEqualTo(409);
        assertThat(r.text("code")).isEqualTo("email-taken");
    }

    @Test
    void cincoFalhasBloqueiamAConta() {
        militar("ana.silva@gnr.test", "Ana Silva", "Guarda");
        Client c = client();
        for (int i = 0; i < 5; i++) {
            assertThat(c.post("/api/v1/auth/login", Map.of("email", "ana.silva@gnr.test", "password", "errada-errada")).status())
                    .isEqualTo(401);
        }
        var locked = c.post("/api/v1/auth/login", Map.of("email", "ana.silva@gnr.test", "password", "palavra-passe-segura"));
        assertThat(locked.status()).isEqualTo(423);
        assertThat(locked.text("code")).isEqualTo("account-locked");
    }

    @Test
    void refreshRodaOTokenEReutilizacaoRevogaASessao() {
        Client c = militar("ana.silva@gnr.test", "Ana Silva", "Guarda");
        String first = c.cookies().get(RT).getValue();

        assertThat(c.post("/api/v1/auth/refresh", null).status()).isEqualTo(200);
        String second = c.cookies().get(RT).getValue();
        assertThat(second).isNotEqualTo(first);

        // Um atacante reutiliza o refresh token antigo
        Client thief = client();
        thief.cookies().put(RT, new Cookie(RT, first));
        assertThat(thief.post("/api/v1/auth/refresh", null).status()).isEqualTo(401);

        // A sessão inteira foi revogada: o dono também perde o acesso
        assertThat(c.get("/api/v1/me").status()).isEqualTo(401);
        assertThat(c.post("/api/v1/auth/refresh", null).status()).isEqualTo(401);
    }

    @Test
    void tokenDeAcessoExpiradoRenovaComRefresh() {
        Client c = militar("ana.silva@gnr.test", "Ana Silva", "Guarda");
        clock.advance(java.time.Duration.ofMinutes(16));
        assertThat(c.get("/api/v1/me").status()).isEqualTo(401);
        assertThat(c.post("/api/v1/auth/refresh", null).status()).isEqualTo(200);
        assertThat(c.get("/api/v1/me").status()).isEqualTo(200);
    }

    @Test
    void logoutInvalidaOTokenDeAcessoDeImediato() {
        Client c = militar("ana.silva@gnr.test", "Ana Silva", "Guarda");
        Cookie access = c.cookies().get(AT);

        assertThat(c.post("/api/v1/auth/logout", null).status()).isEqualTo(204);

        Client replay = client();
        replay.cookies().put(AT, access);
        assertThat(replay.get("/api/v1/me").status()).isEqualTo(401);
    }
}
