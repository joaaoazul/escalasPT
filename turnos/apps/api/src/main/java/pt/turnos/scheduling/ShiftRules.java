package pt.turnos.scheduling;

import java.time.Duration;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Objects;

/**
 * Regras de compatibilidade entre serviços do mesmo militar (portadas do conflict_detector.py do EscalasPT):
 * <ol>
 *   <li>Folga e ausências (dia inteiro) não admitem outro serviço nesse dia.</li>
 *   <li>Serviço normal: no máximo um por dia; os acumuláveis (GRAT) podem juntar-se a ele.</li>
 *   <li>Nunca há sobreposição horária (também garantida pela BD).</li>
 *   <li>Descanso mínimo entre serviços: só aviso.</li>
 * </ol>
 * É uma função pura: recebe o que o militar já tem e o que se propõe, devolve violações.
 */
public final class ShiftRules {

    public static final Duration MIN_REST = Duration.ofHours(8);
    private static final DateTimeFormatter DAY = DateTimeFormatter.ofPattern("dd/MM");

    private ShiftRules() {
    }

    /** Valida {@code proposed} contra {@code existing} (serviços do mesmo militar, já sem os que vão ser substituídos). */
    public static List<Violation> check(Collection<ShiftInfo> existing, ShiftInfo proposed) {
        List<Violation> out = new ArrayList<>();
        for (ShiftInfo other : existing) {
            if (Objects.equals(other.id(), proposed.id())) {
                continue;
            }
            boolean sameDay = other.date().equals(proposed.date());
            if (sameDay && proposed.allDay()) {
                out.add(error("FULL_DAY", proposed, proposed.type().name() + " não pode coexistir com " + other.type().code()
                        + " em " + DAY.format(proposed.date())));
                continue;
            }
            if (sameDay && other.allDay()) {
                out.add(error("FULL_DAY", proposed, "Já tem " + other.type().code() + " em " + DAY.format(proposed.date())
                        + " e não pode acumular serviços"));
                continue;
            }
            if (proposed.allDay() || other.allDay()) {
                continue;
            }
            boolean overlap = proposed.startsAt().isBefore(other.endsAt()) && other.startsAt().isBefore(proposed.endsAt());
            if (overlap) {
                out.add(error("OVERLAP", proposed, "Sobreposição horária com " + other.type().code() + " de " + DAY.format(other.date())));
                continue;
            }
            if (sameDay && normal(proposed) && normal(other)) {
                out.add(error("SECOND_SERVICE", proposed, "Já tem " + other.type().code() + " em " + DAY.format(proposed.date())
                        + " (máximo um serviço normal por dia)"));
                continue;
            }
            Duration gap = !proposed.startsAt().isBefore(other.endsAt())
                    ? Duration.between(other.endsAt(), proposed.startsAt())
                    : Duration.between(proposed.endsAt(), other.startsAt());
            if (!gap.isNegative() && gap.compareTo(MIN_REST) < 0) {
                out.add(new Violation("MIN_REST", Violation.Severity.WARNING, proposed.date(),
                        "Só " + hours(gap) + " h de descanso entre " + other.type().code() + " e " + proposed.type().code()));
            }
        }
        return out;
    }

    private static boolean normal(ShiftInfo s) {
        return s.type().work() && !s.type().accumulable();
    }

    private static Violation error(String code, ShiftInfo s, String msg) {
        return new Violation(code, Violation.Severity.ERROR, s.date(), msg);
    }

    private static String hours(Duration d) {
        long m = d.toMinutes();
        return m % 60 == 0 ? String.valueOf(m / 60) : String.format("%.1f", m / 60.0).replace('.', ',');
    }
}
