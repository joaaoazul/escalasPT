package pt.turnos.swaps;

import static org.assertj.core.api.Assertions.assertThat;

import java.security.MessageDigest;
import java.time.Instant;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpMethod;

import tools.jackson.databind.JsonNode;
import pt.turnos.support.Client;
import pt.turnos.support.IntegrationTest;
import pt.turnos.swaps.internal.SwapExpiryJob;

class SwapIntegrationTest extends IntegrationTest {

    @Autowired
    private SwapExpiryJob expiryJob;

    private Posto p;
    private Client ana;   // Grupo 1
    private Client rui;   // Grupo 2 (outro grupo de folgas, mesmo posto)

    @BeforeEach
    void setUp() {
        p = posto();
        ana = membro(p.cmd1(), p.grupo1(), "ana@gnr.test", "Ana Silva", "Guarda");
        rui = membro(p.cmd2(), p.grupo2(), "rui@gnr.test", "Rui Rocha", "Cabo");
    }

    private String type(String code) {
        for (JsonNode t : ana.get("/api/v1/postos/" + p.postoId() + "/shift-types").body()) {
            if (t.path("code").asString().equals(code)) {
                return t.path("id").asString();
            }
        }
        throw new IllegalArgumentException(code);
    }

    private String paint(Client c, String code, String date) {
        var r = c.put("/api/v1/me/shifts/paint", Map.of("shiftTypeId", type(code), "dates", List.of(date)));
        assertThat(r.status()).as(r.body().toString()).isEqualTo(200);
        return r.body().path("shifts").get(0).path("id").asString();
    }

    private Client.Res pedir(Client c, String myShift, String theirShift) {
        return c.post("/api/v1/swaps", Map.of("shiftId", myShift, "targetShiftId", theirShift, "message", "Tenho tribunal"));
    }

    private String code(Client c, String date) {
        JsonNode s = c.get("/api/v1/me/shifts?from=" + date + "&to=" + date).body();
        return s.isEmpty() ? null : s.get(0).path("code").asString();
    }

    @Test
    void camaradaAceitaEOsServicosTrocamComDocumentoEmitido() throws Exception {
        String a = paint(ana, "AT2", "2026-10-07");
        String b = paint(rui, "OC3", "2026-10-07");

        var req = pedir(ana, a, b);
        assertThat(req.status()).isEqualTo(201);
        assertThat(req.text("status")).isEqualTo("PENDENTE");
        assertThat(req.body().path("expiresAt").asString()).isEqualTo("2026-10-06T23:00:00Z"); // fim da véspera, hora de Lisboa
        String id = req.text("id");

        assertThat(rui.get("/api/v1/me/swaps?box=received").body()).hasSize(1);
        assertThat(ana.get("/api/v1/me/swaps?box=sent").body()).hasSize(1);

        var ok = rui.post("/api/v1/swaps/" + id + "/accept", null);
        assertThat(ok.status()).as(ok.body().toString()).isEqualTo(200);
        assertThat(ok.text("status")).isEqualTo("ACEITE");
        assertThat(ok.text("documentReference")).matches("[0-9A-F]{8}");

        assertThat(code(ana, "2026-10-07")).isEqualTo("OC3");
        assertThat(code(rui, "2026-10-07")).isEqualTo("AT2");

        // O documento chega aos dois e é o formulário oficial, sem a autorização do comandante
        var pdf = ana.get("/api/v1/swaps/" + id + "/document.pdf").raw();
        assertThat(pdf.getContentType()).isEqualTo("application/pdf");
        byte[] bytes = pdf.getContentAsByteArray();
        assertThat(pdf.getHeader("X-Content-SHA256"))
                .isEqualTo(HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)));
        assertThat(rui.get("/api/v1/swaps/" + id + "/document.pdf").raw().getContentAsByteArray()).isEqualTo(bytes);

        String text;
        try (PDDocument doc = Loader.loadPDF(bytes)) {
            // Como o formulário gerado pelo EscalasPT: a NOTA do Art. 34.º passa para a segunda página
            assertThat(doc.getNumberOfPages()).isEqualTo(2);
            text = new PDFTextStripper().getText(doc).replace('\u00a0', ' ').replaceAll("\\s+", " ");
        }
        assertThat(text)
                .contains("Ministério da Administração Interna", "GUARDA NACIONAL REPUBLICANA", "Posto Territorial de Castro Marim",
                        "VISTO", "TROCA DE SERVIÇO")
                .contains("Declaro que desejo efectuar uma troca de serviço de Atendimento (08h-16h) no dia 07/10/2026")
                .contains("08:00", "16:00", "Guarda Ana Silva", "Cabo Rui Rocha", "Patrulha (16h-00h)", "00:00")
                .contains("Quartel em Castro Marim, 26 de setembro de 2026")
                .contains("O DECLARANTE", "CONFIRMO A TROCA", "REGISTO DIGITAL")
                .contains("Pedido de troca: 26/09/2026 às 11:00", "Aceitação pelo militar: 26/09/2026 às 11:00")
                .contains("Artigo 34.º (Trocas de serviço)", "até à véspera da execução")
                .contains("Processado por computador", "Ref. " + ok.text("documentReference") + " · Página 2 de 2")
                .doesNotContain("Comandante");
    }

    @Test
    void camaradaPedeParaAguardarEDepoisRecusa() {
        String id = pedir(ana, paint(ana, "AT2", "2026-10-07"), paint(rui, "OC3", "2026-10-07")).text("id");

        assertThat(ana.post("/api/v1/swaps/" + id + "/hold", null).status()).isEqualTo(403); // quem pediu não responde
        var held = rui.post("/api/v1/swaps/" + id + "/hold", Map.of("message", "Vejo em casa e digo-te"));
        assertThat(held.text("status")).isEqualTo("EM_ESPERA");
        assertThat(held.text("holdMessage")).isEqualTo("Vejo em casa e digo-te");

        var no = rui.post("/api/v1/swaps/" + id + "/decline", Map.of("message", "Afinal não dá"));
        assertThat(no.text("status")).isEqualTo("RECUSADA");
        assertThat(no.text("declineReason")).isEqualTo("Afinal não dá");
        assertThat(code(ana, "2026-10-07")).isEqualTo("AT2");
        assertThat(rui.post("/api/v1/swaps/" + id + "/accept", null).text("code")).isEqualTo("swap-invalid-state");
        assertThat(ana.get("/api/v1/me/swaps?box=history").body()).hasSize(1);
    }

    @Test
    void soQuemPediuCancela() {
        String id = pedir(ana, paint(ana, "AT2", "2026-10-07"), paint(rui, "OC3", "2026-10-07")).text("id");
        assertThat(rui.post("/api/v1/swaps/" + id + "/cancel", null).status()).isEqualTo(403);
        assertThat(ana.post("/api/v1/swaps/" + id + "/cancel", null).text("status")).isEqualTo("CANCELADA");
    }

    @Test
    void pedidoSoAteAVesperaEExpiraAutomaticamente() {
        String a = paint(ana, "AT2", "2026-09-26"), b = paint(rui, "OC3", "2026-09-26");
        assertThat(pedir(ana, a, b).text("code")).isEqualTo("too-late");

        String id = pedir(ana, paint(ana, "AT2", "2026-10-07"), paint(rui, "OC3", "2026-10-07")).text("id");
        clock.set(Instant.parse("2026-10-06T22:59:00Z")); // 23:59 de 6/10 em Lisboa: ainda vale
        refresh(ana, rui);
        assertThat(rui.post("/api/v1/swaps/" + id + "/hold", null).status()).isEqualTo(200);

        clock.set(Instant.parse("2026-10-06T23:00:00Z")); // 00:00 do próprio dia
        refresh(ana, rui);
        var late = rui.post("/api/v1/swaps/" + id + "/accept", null);
        assertThat(late.text("code")).isEqualTo("swap-expired");
        assertThat(ana.get("/api/v1/swaps/" + id).text("status")).isEqualTo("EXPIRADA");
    }

    @Test
    void jobExpiraPedidosSemResposta() {
        String id = pedir(ana, paint(ana, "AT2", "2026-10-07"), paint(rui, "OC3", "2026-10-07")).text("id");
        clock.set(Instant.parse("2026-10-06T22:59:59Z"));
        assertThat(expiryJob.run()).isZero();
        clock.set(Instant.parse("2026-10-06T23:00:00Z"));
        assertThat(expiryJob.run()).isEqualTo(1);
        refresh(ana);
        assertThat(ana.get("/api/v1/swaps/" + id).text("status")).isEqualTo("EXPIRADA");
    }

    @Test
    void ausenciasNaoSeTrocam() {
        var r = pedir(ana, paint(ana, "FER", "2026-10-07"), paint(rui, "OC3", "2026-10-07"));
        assertThat(r.text("code")).isEqualTo("type-not-swappable");
    }

    @Test
    void naoSeTrocaOMesmoServicoNoMesmoDia() {
        var r = pedir(ana, paint(ana, "AT2", "2026-10-07"), paint(rui, "AT2", "2026-10-07"));
        assertThat(r.text("code")).isEqualTo("same-service");
    }

    @Test
    void trocaQueCriaConflitoEBloqueada() {
        String a = paint(ana, "AT2", "2026-10-07");
        Map<String, Object> grat = new HashMap<>(Map.of("shiftTypeId", type("GRAT"), "date", "2026-10-07", "start", "18:00", "durationMinutes", 240));
        assertThat(ana.post("/api/v1/me/shifts", grat).status()).isEqualTo(201);
        var r = pedir(ana, a, paint(rui, "OC3", "2026-10-07"));
        assertThat(r.status()).isEqualTo(422);
        assertThat(r.text("code")).isEqualTo("swap-conflict");
        assertThat(r.body().path("violations").get(0).path("code").asString()).isEqualTo("OVERLAP");
    }

    @Test
    void descansoCurtoEAvisoMasDeixaPedir() {
        paint(ana, "AT1", "2026-10-08");
        var r = pedir(ana, paint(ana, "AT2", "2026-10-07"), paint(rui, "AT3", "2026-10-07"));
        assertThat(r.status()).isEqualTo(201);
        assertThat(r.body().path("warnings").get(0).path("code").asString()).isEqualTo("MIN_REST");
    }

    @Test
    void soMilitaresDoMesmoPosto() {
        Client admin = p.admin();
        String outroPosto = admin.post("/api/v1/postos", Map.of("name", "Posto Territorial de Tavira", "location", "Tavira")).text("id");
        String g = admin.post("/api/v1/postos/" + outroPosto + "/groups", Map.of("name", "Grupo 1")).text("id");
        Client ze = militar("ze@gnr.test", "José Costa", "Guarda");
        join(ze, admin.post("/api/v1/groups/" + g + "/invites", Map.of()).text("code"));
        String zeShift = ze.put("/api/v1/me/shifts/paint", Map.of("shiftTypeId",
                ze.get("/api/v1/postos/" + outroPosto + "/shift-types").body().get(1).path("id").asString(),
                "dates", List.of("2026-10-07"))).body().path("shifts").get(0).path("id").asString();

        assertThat(pedir(ana, paint(ana, "OC3", "2026-10-07"), zeShift).status()).isEqualTo(404);
    }

    @Test
    void servicoAlteradoDepoisDoPedidoCancelaNaAceitacao() {
        String a = paint(ana, "AT2", "2026-10-07");
        String id = pedir(ana, a, paint(rui, "OC3", "2026-10-07")).text("id");
        assertThat(ana.delete("/api/v1/shifts/" + a).text("code")).isEqualTo("shift-has-active-swap");
        assertThat(ana.patch("/api/v1/shifts/" + a, Map.of("version", 0, "notes", "mudei")).status()).isEqualTo(200);

        var r = rui.post("/api/v1/swaps/" + id + "/accept", null);
        assertThat(r.status()).isEqualTo(409);
        assertThat(r.text("code")).isEqualTo("shift-changed");
        assertThat(ana.get("/api/v1/swaps/" + id).text("status")).isEqualTo("CANCELADA");
    }

    @Test
    void umSoPedidoAtivoPorServico() {
        Client ze = membro(p.cmd1(), p.grupo1(), "ze@gnr.test", "José Costa", "Guarda");
        String b = paint(rui, "OC3", "2026-10-07");
        assertThat(pedir(ana, paint(ana, "AT2", "2026-10-07"), b).status()).isEqualTo(201);
        assertThat(pedir(ze, paint(ze, "AT1", "2026-10-07"), b).text("code")).isEqualTo("swap-already-active");
    }

    @Test
    void quemNaoEstaNaTrocaNaoAVe() {
        String id = pedir(ana, paint(ana, "AT2", "2026-10-07"), paint(rui, "OC3", "2026-10-07")).text("id");
        assertThat(p.cmd1().get("/api/v1/swaps/" + id).status()).isEqualTo(404);
        assertThat(p.cmd1().post("/api/v1/swaps/" + id + "/accept", null).status()).isEqualTo(404);
    }

    @Test
    void sairDoGrupoCancelaOsPedidosAtivos() {
        String id = pedir(ana, paint(ana, "AT2", "2026-10-07"), paint(rui, "OC3", "2026-10-07")).text("id");
        assertThat(rui.delete("/api/v1/groups/" + p.grupo2() + "/members/" + userId(rui)).status()).isEqualTo(204);
        assertThat(ana.get("/api/v1/swaps/" + id).text("status")).isEqualTo("CANCELADA");
    }

    @Test
    void aceitarECancelarAoMesmoTempoSoUmGanha() throws Exception {
        for (int round = 0; round < 5; round++) {
            String date = "2026-10-1" + round;
            String id = pedir(ana, paint(ana, "AT2", date), paint(rui, "OC3", date)).text("id");
            CountDownLatch go = new CountDownLatch(1);
            ExecutorService pool = Executors.newFixedThreadPool(2);
            Future<Integer> accept = pool.submit(() -> { go.await(); return rui.send(HttpMethod.POST, "/api/v1/swaps/" + id + "/accept", null).status(); });
            Future<Integer> cancel = pool.submit(() -> { go.await(); return ana.send(HttpMethod.POST, "/api/v1/swaps/" + id + "/cancel", null).status(); });
            go.countDown();
            List<Integer> statuses = List.of(accept.get(), cancel.get());
            pool.shutdown();

            assertThat(statuses).containsOnlyOnce(200).contains(409);
            String status = ana.get("/api/v1/swaps/" + id).text("status");
            long docs = jdbc.sql("SELECT count(*) FROM swap_documents WHERE swap_request_id = CAST(:id AS uuid)").param("id", id)
                    .query(Long.class).single();
            assertThat(docs).isEqualTo(status.equals("ACEITE") ? 1 : 0);
            assertThat(code(ana, date)).isEqualTo(status.equals("ACEITE") ? "OC3" : "AT2");
        }
    }
}
