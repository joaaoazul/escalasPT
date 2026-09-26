package pt.turnos.units;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Map;

import org.junit.jupiter.api.Test;

import pt.turnos.support.Client;
import pt.turnos.support.IntegrationTest;

class UnitsIntegrationTest extends IntegrationTest {

    @Test
    void soOAdministradorCriaPostos() {
        Client ana = militar("ana@gnr.test", "Ana Silva", "Guarda");
        var r = ana.post("/api/v1/postos", Map.of("name", "Posto X", "location", "X"));
        assertThat(r.status()).isEqualTo(403);
    }

    @Test
    void comandanteDeGrupoConvidaEOMilitarEntra() {
        Posto p = posto();
        Client ana = militar("ana@gnr.test", "Ana Silva", "Guarda");
        String code = p.cmd1().post("/api/v1/groups/" + p.grupo1() + "/invites",
                Map.of("email", "ana@gnr.test", "name", "Ana Silva", "rank", "Guarda")).text("code");
        assertThat(code).matches("[0-9A-Z]{5}(-[0-9A-Z]{5}){3}");

        var preview = ana.get("/api/v1/invites/" + code);
        assertThat(preview.text("groupName")).isEqualTo("Grupo 1");
        assertThat(preview.text("invitedBy")).isEqualTo("Cabo-Chefe Sofia Matos");
        assertThat(preview.text("status")).isEqualTo("PENDING");

        var joined = ana.post("/api/v1/invites/" + code.toLowerCase() + "/accept", null);
        assertThat(joined.status()).isEqualTo(200);
        assertThat(joined.text("groupName")).isEqualTo("Grupo 1");
        assertThat(joined.body().path("commander").asBoolean()).isFalse();

        var posto = ana.get("/api/v1/postos/" + p.postoId());
        assertThat(posto.status()).isEqualTo(200);
        assertThat(posto.body().path("groups").get(0).path("members")).hasSize(2);
        assertThat(p.cmd1().get("/api/v1/groups/" + p.grupo1() + "/invites").body().get(0).path("status").asString())
                .isEqualTo("ACCEPTED");
    }

    @Test
    void conviteEDeUsoUnicoEPessoal() {
        Posto p = posto();
        String code = p.cmd1().post("/api/v1/groups/" + p.grupo1() + "/invites", Map.of("email", "ana@gnr.test")).text("code");

        Client outro = militar("rui@gnr.test", "Rui Rocha", "Cabo");
        assertThat(outro.post("/api/v1/invites/" + code + "/accept", null).status()).isEqualTo(403);

        Client ana = militar("ana@gnr.test", "Ana Silva", "Guarda");
        assertThat(ana.post("/api/v1/invites/" + code + "/accept", null).status()).isEqualTo(200);
        var again = ana.post("/api/v1/invites/" + code + "/accept", null);
        assertThat(again.text("code")).isEqualTo("invite-accepted");
    }

    @Test
    void soOComandanteDeGrupoConvida() {
        Posto p = posto();
        Client ana = membro(p.cmd1(), p.grupo1(), "ana@gnr.test", "Ana Silva", "Guarda");
        assertThat(ana.post("/api/v1/groups/" + p.grupo1() + "/invites", Map.of()).status()).isEqualTo(403);
        // O comandante de outro grupo também não
        assertThat(p.cmd2().post("/api/v1/groups/" + p.grupo1() + "/invites", Map.of()).status()).isEqualTo(403);
        // E ninguém que não seja administrador nomeia comandantes
        assertThat(p.cmd1().post("/api/v1/groups/" + p.grupo1() + "/invites", Map.of("role", "COMMANDER")).status()).isEqualTo(403);
    }

    @Test
    void conviteRevogadoNaoServe() {
        Posto p = posto();
        var inv = p.cmd1().post("/api/v1/groups/" + p.grupo1() + "/invites", Map.of());
        assertThat(p.cmd1().delete("/api/v1/groups/" + p.grupo1() + "/invites/" + inv.text("id")).status()).isEqualTo(204);
        Client ana = militar("ana@gnr.test", "Ana Silva", "Guarda");
        assertThat(ana.post("/api/v1/invites/" + inv.text("code") + "/accept", null).text("code")).isEqualTo("invite-revoked");
    }

    @Test
    void umMilitarSoPertenceAUmGrupo() {
        Posto p = posto();
        Client ana = membro(p.cmd1(), p.grupo1(), "ana@gnr.test", "Ana Silva", "Guarda");
        String code = p.cmd2().post("/api/v1/groups/" + p.grupo2() + "/invites", Map.of()).text("code");
        assertThat(ana.post("/api/v1/invites/" + code + "/accept", null).text("code")).isEqualTo("already-member");
    }

    @Test
    void listaDePostos() {
        Posto p = posto();
        militar("x@gnr.test", "Xavier", "Guarda");
        assertThat(p.admin().get("/api/v1/postos").body()).hasSize(1);
        assertThat(p.cmd1().get("/api/v1/postos").body().get(0).path("groups")).hasSize(2);
        assertThat(client().post("/api/v1/auth/login", Map.of("email", "x@gnr.test", "password", "palavra-passe-segura")).status()).isEqualTo(200);
    }

    @Test
    void postoSoEVisivelAosSeusMilitares() {
        Posto p = posto();
        Client estranho = militar("x@gnr.test", "Xavier", "Guarda");
        assertThat(estranho.get("/api/v1/postos/" + p.postoId()).status()).isEqualTo(404);
    }

    @Test
    void comandanteRemoveMilitarMasNaoSaiSemPassarOComando() {
        Posto p = posto();
        Client ana = membro(p.cmd1(), p.grupo1(), "ana@gnr.test", "Ana Silva", "Guarda");
        String anaId = userId(ana);
        String cmdId = userId(p.cmd1());

        assertThat(p.cmd1().delete("/api/v1/groups/" + p.grupo1() + "/members/" + cmdId).text("code"))
                .isEqualTo("commander-must-transfer");
        assertThat(p.cmd1().post("/api/v1/groups/" + p.grupo1() + "/commander", Map.of("userId", anaId)).status()).isEqualTo(204);
        assertThat(ana.get("/api/v1/me/membership").body().path("commander").asBoolean()).isTrue();

        assertThat(ana.delete("/api/v1/groups/" + p.grupo1() + "/members/" + cmdId).status()).isEqualTo(204);
        assertThat(p.cmd1().get("/api/v1/me/membership").status()).isEqualTo(404);
    }
}
