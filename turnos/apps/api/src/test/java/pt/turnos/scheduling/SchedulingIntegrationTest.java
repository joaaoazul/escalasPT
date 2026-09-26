package pt.turnos.scheduling;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;

import tools.jackson.databind.JsonNode;
import pt.turnos.support.Client;
import pt.turnos.support.IntegrationTest;

class SchedulingIntegrationTest extends IntegrationTest {

    private String type(Client c, String postoId, String code) {
        for (JsonNode t : c.get("/api/v1/postos/" + postoId + "/shift-types").body()) {
            if (t.path("code").asString().equals(code)) {
                return t.path("id").asString();
            }
        }
        throw new IllegalArgumentException(code);
    }

    private Client.Res paint(Client c, String typeId, String... dates) {
        Map<String, Object> body = new HashMap<>();
        body.put("shiftTypeId", typeId);
        body.put("dates", List.of(dates));
        return c.put("/api/v1/me/shifts/paint", body);
    }

    @Test
    void postoNovoTemOsTiposDeServicoDoEscalasPT() {
        Posto p = posto();
        var types = p.cmd1().get("/api/v1/postos/" + p.postoId() + "/shift-types").body();
        assertThat(types).hasSize(17);
        assertThat(types.get(0).path("code").asString()).isEqualTo("AT1");
        assertThat(types.get(0).path("startTime").asString()).isEqualTo("00:00:00");
    }

    @Test
    void pincelPreencheESubstituiDias() {
        Posto p = posto();
        Client ana = membro(p.cmd1(), p.grupo1(), "ana@gnr.test", "Ana Silva", "Guarda");
        String at2 = type(ana, p.postoId(), "AT2"), folga = type(ana, p.postoId(), "F");

        var r = paint(ana, at2, "2026-10-05", "2026-10-06", "2026-10-07");
        assertThat(r.status()).isEqualTo(200);
        assertThat(r.body().path("shifts")).hasSize(3);

        assertThat(paint(ana, folga, "2026-10-06").status()).isEqualTo(200);
        var mine = ana.get("/api/v1/me/shifts?from=2026-10-01&to=2026-10-31").body();
        assertThat(mine).hasSize(3);
        assertThat(mine.get(1).path("code").asString()).isEqualTo("F");
        assertThat(mine.get(1).path("allDay").asBoolean()).isTrue();

        // Limpar
        assertThat(paint(ana, null, "2026-10-05").status()).isEqualTo(200);
        assertThat(ana.get("/api/v1/me/shifts?from=2026-10-01&to=2026-10-31").body()).hasSize(2);
    }

    @Test
    void mudancaDeHoraUsaHorasReais() {
        Posto p = posto();
        Client ana = membro(p.cmd1(), p.grupo1(), "ana@gnr.test", "Ana Silva", "Guarda");
        var s = paint(ana, type(ana, p.postoId(), "AT1"), "2026-10-25").body().path("shifts").get(0);
        assertThat(s.path("startsAt").asString()).isEqualTo("2026-10-24T23:00:00Z");
        assertThat(s.path("endsAt").asString()).isEqualTo("2026-10-25T07:00:00Z");
    }

    @Test
    void gratificadoPrecisaDeHorasEAcumulaSemSobrepor() {
        Posto p = posto();
        Client ana = membro(p.cmd1(), p.grupo1(), "ana@gnr.test", "Ana Silva", "Guarda");
        paint(ana, type(ana, p.postoId(), "AT2"), "2026-10-07");
        String grat = type(ana, p.postoId(), "GRAT");

        var semHoras = ana.post("/api/v1/me/shifts", Map.of("shiftTypeId", grat, "date", "2026-10-07"));
        assertThat(semHoras.text("code")).isEqualTo("hours-required");

        var sobreposto = ana.post("/api/v1/me/shifts", Map.of("shiftTypeId", grat, "date", "2026-10-07", "start", "14:00", "durationMinutes", 240));
        assertThat(sobreposto.status()).isEqualTo(422);
        assertThat(sobreposto.body().path("violations").get(0).path("code").asString()).isEqualTo("OVERLAP");

        var ok = ana.post("/api/v1/me/shifts", Map.of("shiftTypeId", grat, "date", "2026-10-07", "start", "18:00", "durationMinutes", 240));
        assertThat(ok.status()).isEqualTo(201);
        assertThat(ok.body().path("warnings").get(0).path("code").asString()).isEqualTo("MIN_REST");
    }

    @Test
    void segundoServicoNormalNoDiaEBloqueado() {
        Posto p = posto();
        Client ana = membro(p.cmd1(), p.grupo1(), "ana@gnr.test", "Ana Silva", "Guarda");
        paint(ana, type(ana, p.postoId(), "AT1"), "2026-10-07");
        var r = ana.post("/api/v1/me/shifts", Map.of("shiftTypeId", type(ana, p.postoId(), "AT3"), "date", "2026-10-07"));
        assertThat(r.status()).isEqualTo(422);
        assertThat(r.text("code")).isEqualTo("shift-conflict");
        assertThat(r.body().path("violations").get(0).path("code").asString()).isEqualTo("SECOND_SERVICE");
    }

    @Test
    void escalaDoPostoEDoGrupo() {
        Posto p = posto();
        Client ana = membro(p.cmd1(), p.grupo1(), "ana@gnr.test", "Ana Silva", "Guarda");
        Client rui = membro(p.cmd2(), p.grupo2(), "rui@gnr.test", "Rui Rocha", "Cabo");
        paint(ana, type(ana, p.postoId(), "AT2"), "2026-10-07");
        paint(rui, type(rui, p.postoId(), "OC2"), "2026-10-07");

        String base = "/api/v1/postos/" + p.postoId() + "/shifts?from=2026-10-01&to=2026-10-31";
        assertThat(ana.get(base).body()).hasSize(2);
        assertThat(ana.get(base + "&groupId=" + p.grupo2()).body()).hasSize(1);
        assertThat(ana.get("/api/v1/users/" + userId(rui) + "/shifts?from=2026-10-01&to=2026-10-31").body()).hasSize(1);

        Client estranho = militar("x@gnr.test", "Xavier", "Guarda");
        assertThat(estranho.get(base).status()).isEqualTo(404);
        assertThat(ana.get("/api/v1/postos/" + p.postoId() + "/shifts?from=2026-01-01&to=2026-12-31").text("code"))
                .isEqualTo("invalid-range");
    }

    @Test
    void notasComControloDeVersao() {
        Posto p = posto();
        Client ana = membro(p.cmd1(), p.grupo1(), "ana@gnr.test", "Ana Silva", "Guarda");
        String id = paint(ana, type(ana, p.postoId(), "AT2"), "2026-10-07").body().path("shifts").get(0).path("id").asString();

        assertThat(ana.patch("/api/v1/shifts/" + id, Map.of("version", 0, "notes", "Levar colete")).body().path("version").asInt())
                .isEqualTo(1);
        assertThat(ana.patch("/api/v1/shifts/" + id, Map.of("version", 0, "notes", "outra")).status()).isEqualTo(409);

        Client rui = membro(p.cmd1(), p.grupo1(), "rui@gnr.test", "Rui Rocha", "Cabo");
        assertThat(rui.delete("/api/v1/shifts/" + id).status()).isEqualTo(404);
        assertThat(ana.delete("/api/v1/shifts/" + id).status()).isEqualTo(204);
    }
}
