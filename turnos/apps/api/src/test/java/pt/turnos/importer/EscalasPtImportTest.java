package pt.turnos.importer;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.LocalDate;
import java.util.Map;
import java.util.UUID;

import javax.sql.DataSource;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;

import com.zaxxer.hikari.HikariDataSource;

import pt.turnos.importer.internal.EscalasPtImporter;
import pt.turnos.support.Client;
import pt.turnos.support.IntegrationTest;

/** A base de dados do EscalasPT é simulada num esquema à parte, com as mesmas tabelas e colunas usadas pela importação. */
class EscalasPtImportTest extends IntegrationTest {

    private static final String OLD_PASSWORD = "palavra-antiga-123";
    private static final UUID STATION = UUID.randomUUID();
    private static final UUID ANA = UUID.randomUUID(), RUI = UUID.randomUUID();
    private static final UUID AT1 = UUID.randomUUID(), AT2 = UUID.randomUUID(), GRAT = UUID.randomUUID(), F = UUID.randomUUID(), FER = UUID.randomUUID();

    @Autowired
    EscalasPtImporter importer;
    @Autowired
    DataSource dataSource;

    DataSource escalasPt;

    @BeforeEach
    void escalasPtDatabase() {
        jdbc.sql("DROP SCHEMA IF EXISTS escalaspt CASCADE").update();
        jdbc.sql("CREATE SCHEMA escalaspt").update();
        jdbc.sql("""
                CREATE TABLE escalaspt.stations (id uuid PRIMARY KEY, name text, code text, comando_territorial text, destacamento text, is_active boolean);
                CREATE TABLE escalaspt.users (id uuid PRIMARY KEY, username text, email text, password_hash text, full_name text, nip text,
                    numero_ordem text, role text, station_id uuid, is_active boolean);
                CREATE TABLE escalaspt.shift_types (id uuid PRIMARY KEY, station_id uuid, name text, code text, start_time time, end_time time,
                    color text, min_staff int, is_absence boolean, fixed_slots boolean, is_active boolean);
                CREATE TABLE escalaspt.shifts (id uuid PRIMARY KEY, user_id uuid, station_id uuid, shift_type_id uuid, date date,
                    start_datetime timestamptz, end_datetime timestamptz, status text, notes text)""").update();
        // Hash no formato do passlib do EscalasPT ($2b$, 12 rondas)
        String hash = new BCryptPasswordEncoder(BCryptPasswordEncoder.BCryptVersion.$2B, 12).encode(OLD_PASSWORD);
        jdbc.sql("INSERT INTO escalaspt.stations VALUES (:id, 'Posto Territorial de Castro Marim', 'PT-CMR', 'CT Faro', 'DT Tavira', true)")
                .param("id", STATION).update();
        jdbc.sql("""
                INSERT INTO escalaspt.users VALUES
                  (:ana, 'guarda.silva', 'ana.silva@gnr.pt', :h, 'Ana Silva', '2210477', '909', 'militar', :st, true),
                  (:rui, 'cabo.rocha', 'rui.rocha@gnr.pt', :h, 'Rui Rocha', '2030669', '510', 'militar', :st, true),
                  (gen_random_uuid(), 'saj.cmd', 'cmd@gnr.pt', :h, 'Comandante', '2020879', '53', 'comandante', :st, false),
                  (gen_random_uuid(), 'admin', 'admin@gnr.pt', :h, 'Admin', '0000000', null, 'admin', :st, true)""")
                .param("ana", ANA).param("rui", RUI).param("h", hash).param("st", STATION).update();
        jdbc.sql("""
                INSERT INTO escalaspt.shift_types VALUES
                  (:at1, :st, 'Atendimento (00h-08h)', 'AT1', '00:00', '08:00', '#059669', 1, false, true, true),
                  (:at2, :st, 'Atendimento (08h-16h)', 'AT2', '08:00', '16:00', '#10B981', 1, false, true, true),
                  (:grat, :st, 'Gratificado', 'GRAT', '00:00', '00:00', '#D97706', 1, false, false, true),
                  (:f, :st, 'Folga', 'F', '00:00', '00:00', '#6B7280', 0, false, false, true),
                  (:fer, :st, 'Férias', 'FER', '00:00', '00:00', '#7C3AED', 0, true, false, true)""")
                .param("at1", AT1).param("at2", AT2).param("grat", GRAT).param("f", F).param("fer", FER).param("st", STATION).update();
        jdbc.sql("""
                INSERT INTO escalaspt.shifts VALUES
                  (gen_random_uuid(), :ana, :st, :at2, '2026-10-07', '2026-10-07 08:00+01', '2026-10-07 16:00+01', 'published', null),
                  (gen_random_uuid(), :ana, :st, :at1, '2026-10-07', '2026-10-07 00:00+01', '2026-10-07 08:00+01', 'published', 'Levar colete'),
                  (gen_random_uuid(), :ana, :st, :fer, '2026-10-20', '2026-10-20 00:00+01', '2026-10-20 00:00+01', 'published', null),
                  (gen_random_uuid(), :rui, :st, :grat, '2026-10-07', '2026-10-07 18:00+01', '2026-10-07 22:00+01', 'published', null),
                  (gen_random_uuid(), :rui, :st, :f, '2026-10-08', '2026-10-08 00:00+01', '2026-10-08 00:00+01', 'draft', null),
                  (gen_random_uuid(), :rui, :st, :at2, '2026-01-10', '2026-01-10 08:00+00', '2026-01-10 16:00+00', 'published', null)""")
                .param("ana", ANA).param("rui", RUI).param("st", STATION).param("at1", AT1).param("at2", AT2).param("grat", GRAT)
                .param("f", F).param("fer", FER).update();

        HikariDataSource h = (HikariDataSource) dataSource;
        escalasPt = new DriverManagerDataSource(h.getJdbcUrl() + (h.getJdbcUrl().contains("?") ? "&" : "?") + "currentSchema=escalaspt",
                h.getUsername(), h.getPassword());
    }

    private EscalasPtImporter.Report importar() {
        return importer.run(escalasPt, new EscalasPtImporter.Options("PT-CMR", "Grupo 1", "ana.silva@gnr.pt", LocalDate.parse("2026-09-01")));
    }

    @Test
    void importaPostoMilitaresEServicos() {
        EscalasPtImporter.Report r = importar();

        assertThat(r.postoName()).isEqualTo("Posto Territorial de Castro Marim");
        assertThat(r.types()).isEqualTo(5);
        assertThat(r.militaresCreated()).isEqualTo(2);  // o comandante inativo e o admin ficam de fora
        assertThat(r.shifts()).isEqualTo(3);            // AT1 + FER da Ana, GRAT do Rui
        // Dois serviços normais no mesmo dia: fica o primeiro (por hora de início), o outro vai para o relatório
        assertThat(r.skipped()).singleElement().asString().contains("AT2").contains("2026-10-07").contains("máximo um serviço normal");

        // A Ana entra com a palavra-passe que já tinha, e o hash passa a Argon2
        Client ana = client();
        assertThat(ana.post("/api/v1/auth/login", Map.of("email", "ana.silva@gnr.pt", "password", OLD_PASSWORD)).status()).isEqualTo(200);
        assertThat(jdbc.sql("SELECT password_hash FROM users WHERE email = 'ana.silva@gnr.pt'").query(String.class).single()).startsWith("$argon2id$");
        assertThat(ana.post("/api/v1/auth/login", Map.of("email", "ana.silva@gnr.pt", "password", OLD_PASSWORD)).status()).isEqualTo(200);

        var membership = ana.get("/api/v1/me/membership").body();
        assertThat(membership.path("postoName").asString()).isEqualTo("Posto Territorial de Castro Marim");
        assertThat(membership.path("commander").asBoolean()).isTrue();
        assertThat(ana.get("/api/v1/me").body().path("serviceNumber").asString()).isEqualTo("909");

        var shifts = ana.get("/api/v1/me/shifts?from=2026-10-01&to=2026-10-31").body();
        assertThat(shifts).hasSize(2);
        assertThat(shifts.get(0).path("code").asString()).isEqualTo("AT1");
        assertThat(shifts.get(0).path("notes").asString()).isEqualTo("Levar colete");
        assertThat(shifts.get(0).path("source").asString()).isEqualTo("IMPORT");
        assertThat(shifts.get(1).path("code").asString()).isEqualTo("FER");

        Client rui = client();
        rui.post("/api/v1/auth/login", Map.of("email", "rui.rocha@gnr.pt", "password", OLD_PASSWORD));
        var grat = rui.get("/api/v1/me/shifts?from=2026-10-01&to=2026-10-31").body().get(0);
        assertThat(grat.path("code").asString()).isEqualTo("GRAT");
        assertThat(grat.path("start").asString()).isEqualTo("18:00:00");
        assertThat(grat.path("durationMinutes").asInt()).isEqualTo(240);

        // Tipos: F é folga, FER ausência (não trocável), GRAT acumulável com horário variável
        var types = ana.get("/api/v1/postos/" + r.postoId() + "/shift-types").body();
        assertThat(types).anySatisfy(t -> {
            assertThat(t.path("code").asString()).isEqualTo("FER");
            assertThat(t.path("kind").asString()).isEqualTo("ABSENCE");
            assertThat(t.path("swappable").asBoolean()).isFalse();
        });
        assertThat(types).anySatisfy(t -> {
            assertThat(t.path("code").asString()).isEqualTo("GRAT");
            assertThat(t.path("accumulable").asBoolean()).isTrue();
            assertThat(t.path("startTime").isNull()).isTrue();
        });
    }

    @Test
    void naoImportaDuasVezes() {
        importar();
        assertThatThrownBy(this::importar).hasMessageContaining("já existe");
    }

    @Test
    void militarPodeCompletarOPerfil() {
        importar();
        Client ana = client();
        ana.post("/api/v1/auth/login", Map.of("email", "ana.silva@gnr.pt", "password", OLD_PASSWORD));
        var me = ana.patch("/api/v1/me", Map.of("rank", "Guarda")).body();
        assertThat(me.path("rank").asString()).isEqualTo("Guarda");
        assertThat(me.path("fullName").asString()).isEqualTo("Ana Silva");
        assertThat(ana.get("/api/v1/postos/" + ana.get("/api/v1/me/membership").body().path("postoId").asString()).body()
                .path("groups").get(0).path("members").toString()).contains("Guarda Ana Silva");
    }
}
