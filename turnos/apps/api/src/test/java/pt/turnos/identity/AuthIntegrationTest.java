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
        Posto p = posto();
        Client c = membro(p.cmd1(), p.grupo1(), "ana.silva@gnr.test", "Ana Silva", "Guarda");

        assertThat(c.cookies()).containsKeys(AT, RT);
        var me = c.get("/api/v1/me");
        assertThat(me.status()).isEqualTo(200);
        assertThat(me.text("fullName")).isEqualTo("Ana Silva");
        assertThat(me.body().path("admin").asBoolean()).isFalse();
    }

    @Test
    void emailDeBootstrapFicaAdmin() {
        Client admin = registar(null, "admin@turnos.test", "Administrador", null);
        assertThat(admin.get("/api/v1/me").body().path("admin").asBoolean()).isTrue();
    }

    @Test
    void semConviteNaoSeCriaConta() {
        var r = client().post("/api/v1/auth/register", registo(null, "ana@gnr.test", "Ana Silva", "Guarda"));
        assertThat(r.status()).isEqualTo(422);
        assertThat(r.text("code")).isEqualTo("invite-required");
        var falso = client().post("/api/v1/auth/register", registo("AAAAA-BBBBB-CCCCC-DDDDD", "ana@gnr.test", "Ana Silva", "Guarda"));
        assertThat(falso.status()).isEqualTo(404);
        assertThat(jdbc.sql("SELECT count(*) FROM users").query(Long.class).single()).isZero();
    }

    @Test
    void registoComConviteEntraLogoNoGrupo() {
        Posto p = posto();
        String code = p.cmd1().post("/api/v1/groups/" + p.grupo1() + "/invites",
                Map.of("email", "ana@gnr.test", "name", "Ana Silva", "rank", "Guarda")).text("code");

        // A pré-visualização é pública e traz o que o comandante preencheu
        var preview = client().get("/api/v1/invites/" + code);
        assertThat(preview.status()).isEqualTo(200);
        assertThat(preview.text("name")).isEqualTo("Ana Silva");
        assertThat(preview.text("email")).isEqualTo("ana@gnr.test");

        // Convite pessoal: outro email não serve, e não fica conta criada
        var outro = client().post("/api/v1/auth/register", registo(code, "rui@gnr.test", "Rui Rocha", "Cabo"));
        assertThat(outro.status()).isEqualTo(403);
        assertThat(jdbc.sql("SELECT count(*) FROM users WHERE email = 'rui@gnr.test'").query(Long.class).single()).isZero();

        Client ana = registar(code, "ana@gnr.test", "Ana Silva", "Guarda");
        var m = ana.get("/api/v1/me/membership");
        assertThat(m.text("groupName")).isEqualTo("Grupo 1");
        assertThat(m.body().path("commander").asBoolean()).isFalse();
        assertThat(client().get("/api/v1/invites/" + code).text("status")).isEqualTo("ACCEPTED");
    }

    @Test
    void comandanteDaCodigoParaReporPalavraPasse() {
        Posto p = posto();
        Client ana = membro(p.cmd1(), p.grupo1(), "ana@gnr.test", "Ana Silva", "Guarda");
        String anaId = userId(ana);
        String reset = "/api/v1/groups/" + p.grupo1() + "/members/" + anaId + "/password-reset";

        // Só o comandante do grupo dela (ou o administrador)
        assertThat(p.cmd2().post("/api/v1/groups/" + p.grupo2() + "/members/" + anaId + "/password-reset", null).status()).isEqualTo(404);
        assertThat(p.cmd2().post(reset, null).status()).isEqualTo(403);
        assertThat(ana.post("/api/v1/groups/" + p.grupo1() + "/members/" + userId(p.cmd1()) + "/password-reset", null).status())
                .isEqualTo(403);

        String antigo = p.cmd1().post(reset, null).text("code");
        var r = p.cmd1().post(reset, null);
        assertThat(r.status()).isEqualTo(201);
        String code = r.text("code");
        assertThat(code).matches("[0-9A-Z]{4}(-[0-9A-Z]{4}){2}");

        // Um código novo invalida o anterior
        assertThat(client().post("/api/v1/auth/password-reset", Map.of("code", antigo, "password", "nova-palavra-passe")).text("code"))
                .isEqualTo("invalid-reset-code");

        Client telemovel = client();
        var ok = telemovel.post("/api/v1/auth/password-reset", Map.of("code", code.toLowerCase(), "password", "nova-palavra-passe"));
        assertThat(ok.status()).isEqualTo(200);
        assertThat(telemovel.get("/api/v1/me").text("email")).isEqualTo("ana@gnr.test");

        // As sessões antigas terminam, a palavra-passe antiga deixa de servir e o código não se reutiliza
        assertThat(ana.get("/api/v1/me").status()).isEqualTo(401);
        assertThat(client().post("/api/v1/auth/login", Map.of("email", "ana@gnr.test", "password", PASSWORD)).status()).isEqualTo(401);
        assertThat(client().post("/api/v1/auth/login", Map.of("email", "ana@gnr.test", "password", "nova-palavra-passe")).status())
                .isEqualTo(200);
        assertThat(client().post("/api/v1/auth/password-reset", Map.of("code", code, "password", "outra-palavra-passe")).status())
                .isEqualTo(422);
    }

    @Test
    void codigoDeReposicaoExpiraEm24HorasEDesbloqueiaAConta() {
        Posto p = posto();
        Client ana = membro(p.cmd1(), p.grupo1(), "ana@gnr.test", "Ana Silva", "Guarda");
        String reset = "/api/v1/groups/" + p.grupo1() + "/members/" + userId(ana) + "/password-reset";
        for (int i = 0; i < 5; i++) {
            client().post("/api/v1/auth/login", Map.of("email", "ana@gnr.test", "password", "errada-errada"));
        }
        String velho = p.cmd1().post(reset, null).text("code");
        clock.advance(java.time.Duration.ofHours(25));
        assertThat(client().post("/api/v1/auth/password-reset", Map.of("code", velho, "password", "nova-palavra-passe")).status())
                .isEqualTo(422);

        refresh(p.cmd1());
        String code = p.cmd1().post(reset, null).text("code");
        assertThat(client().post("/api/v1/auth/password-reset", Map.of("code", code, "password", "nova-palavra-passe")).status())
                .isEqualTo(200);
        assertThat(client().post("/api/v1/auth/login", Map.of("email", "ana@gnr.test", "password", "nova-palavra-passe")).status())
                .isEqualTo(200);
    }

    @Test
    void mudarPalavraPasseTerminaAsOutrasSessoes() {
        Client ana = militar("ana@gnr.test", "Ana Silva", "Guarda");
        Client tablet = client();
        tablet.post("/api/v1/auth/login", Map.of("email", "ana@gnr.test", "password", PASSWORD));

        assertThat(ana.post("/api/v1/me/password", Map.of("currentPassword", "errada-errada", "newPassword", "nova-palavra-passe"))
                .text("code")).isEqualTo("wrong-password");
        assertThat(ana.post("/api/v1/me/password", Map.of("currentPassword", PASSWORD, "newPassword", "nova-palavra-passe")).status())
                .isEqualTo(204);
        assertThat(ana.get("/api/v1/me").status()).isEqualTo(200);
        assertThat(tablet.get("/api/v1/me").status()).isEqualTo(401);
        assertThat(client().post("/api/v1/auth/login", Map.of("email", "ana@gnr.test", "password", "nova-palavra-passe")).status())
                .isEqualTo(200);
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
        Posto p = posto();
        militar("ana.silva@gnr.test", "Ana Silva", "Guarda");
        String code = p.cmd1().post("/api/v1/groups/" + p.grupo1() + "/invites", Map.of()).text("code");
        var r = client().post("/api/v1/auth/register", registo(code, "ANA.SILVA@gnr.test", "Outra", null));
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
