package pt.turnos.scheduling;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;
import java.util.List;
import java.util.UUID;

import org.junit.jupiter.api.Test;

class ShiftRulesTest {

    private static final ZoneId LX = ZoneId.of("Europe/Lisbon");
    private static final UUID POSTO = UUID.randomUUID();
    private static final UUID USER = UUID.randomUUID();
    private static final LocalDate D = LocalDate.of(2026, 10, 7);

    static ShiftTypeInfo work(String code, String start, boolean accumulable) {
        return new ShiftTypeInfo(UUID.randomUUID(), POSTO, code, code, "WORK", false, start == null ? null : LocalTime.parse(start),
                start == null ? null : 480, "#000000", true, accumulable);
    }

    static final ShiftTypeInfo AT1 = work("AT1", "00:00", false);
    static final ShiftTypeInfo AT2 = work("AT2", "08:00", false);
    static final ShiftTypeInfo AT3 = work("AT3", "16:00", false);
    static final ShiftTypeInfo GRAT = work("GRAT", null, true);
    static final ShiftTypeInfo F = new ShiftTypeInfo(UUID.randomUUID(), POSTO, "F", "Folga", "OFF", true, null, null, "#6B7280", true, false);

    static ShiftInfo shift(ShiftTypeInfo t, LocalDate d) {
        return shift(t, d, t.startTime(), t.durationMinutes());
    }

    static ShiftInfo shift(ShiftTypeInfo t, LocalDate d, LocalTime start, Integer minutes) {
        ShiftTimes.Span s = ShiftTimes.resolve(d, start, minutes, t.allDay(), LX);
        return new ShiftInfo(UUID.randomUUID(), USER, POSTO, t, d, start, minutes, s.startsAt(), s.endsAt(), null, "MANUAL", 0);
    }

    static List<String> codes(List<Violation> v) {
        return v.stream().map(Violation::code).toList();
    }

    @Test
    void folgaNaoAdmiteOutroServicoNoDia() {
        assertThat(codes(ShiftRules.check(List.of(shift(F, D)), shift(AT2, D)))).containsExactly("FULL_DAY");
        assertThat(codes(ShiftRules.check(List.of(shift(AT2, D)), shift(F, D)))).containsExactly("FULL_DAY");
    }

    @Test
    void doisServicosNormaisNoMesmoDiaNao() {
        assertThat(codes(ShiftRules.check(List.of(shift(AT1, D)), shift(AT3, D)))).containsExactly("SECOND_SERVICE");
    }

    @Test
    void gratificadoAcumulaComServicoNormalSemSobreposicao() {
        ShiftInfo grat = shift(GRAT, D, LocalTime.of(17, 0), 240);
        assertThat(ShiftRules.check(List.of(shift(AT2, D)), grat)).extracting(Violation::code).containsExactly("MIN_REST");
        assertThat(ShiftRules.check(List.of(shift(AT2, D)), grat)).noneMatch(Violation::error);
    }

    @Test
    void sobreposicaoHorariaNuncaEPermitida() {
        ShiftInfo grat = shift(GRAT, D, LocalTime.of(14, 0), 240);
        assertThat(codes(ShiftRules.check(List.of(shift(AT2, D)), grat))).containsExactly("OVERLAP");
    }

    @Test
    void poucoDescansoEntreDiasEAvisoNaoErro() {
        List<Violation> v = ShiftRules.check(List.of(shift(AT3, D)), shift(AT1, D.plusDays(1)));
        assertThat(codes(v)).containsExactly("MIN_REST");
        assertThat(v.getFirst().error()).isFalse();
        assertThat(v.getFirst().message()).contains("Só 0 h");
    }

    @Test
    void descansoSuficienteNaoGeraAviso() {
        assertThat(ShiftRules.check(List.of(shift(AT2, D)), shift(AT2, D.plusDays(1)))).isEmpty();
    }
}
