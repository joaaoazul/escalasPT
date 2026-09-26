package pt.turnos.scheduling.internal;

import java.time.Clock;
import java.time.LocalTime;
import java.util.List;
import java.util.UUID;

import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

import pt.turnos.scheduling.ShiftTypeInfo;
import pt.turnos.shared.Ids;
import pt.turnos.units.PostoCreated;

/** Tipos de serviço de um posto novo: os mesmos do seed do EscalasPT (códigos, horários e cores). */
@Component
class DefaultShiftTypes {

    private record Def(String code, String name, String kind, String start, Integer minutes, String color, boolean swappable,
                       boolean accumulable) {
    }

    private static final List<Def> DEFAULTS = List.of(
            new Def("AT1", "Atendimento (00h-08h)", "WORK", "00:00", 480, "#059669", true, false),
            new Def("AT2", "Atendimento (08h-16h)", "WORK", "08:00", 480, "#10B981", true, false),
            new Def("AT3", "Atendimento (16h-00h)", "WORK", "16:00", 480, "#047857", true, false),
            new Def("OC1", "Patrulha (00h-08h)", "WORK", "00:00", 480, "#1E40AF", true, false),
            new Def("OC2", "Patrulha (08h-16h)", "WORK", "08:00", 480, "#2563EB", true, false),
            new Def("OC3", "Patrulha (16h-00h)", "WORK", "16:00", 480, "#1E3A8A", true, false),
            new Def("GRAT", "Gratificado", "WORK", null, null, "#D97706", true, true),
            new Def("T", "Tiro", "WORK", null, null, "#DC2626", true, false),
            new Def("INST", "Instrução", "WORK", null, null, "#9333EA", true, false),
            new Def("INQ", "Inquéritos", "WORK", "09:00", 480, "#B45309", true, false),
            new Def("SEC", "Secretaria", "WORK", "09:00", 480, "#F472B6", true, false),
            new Def("F", "Folga", "OFF", null, null, "#6B7280", true, false),
            new Def("FER", "Férias", "ABSENCE", null, null, "#7C3AED", false, false),
            new Def("CONV", "Convalescença", "ABSENCE", null, null, "#BE185D", false, false),
            new Def("MF", "Morte de Familiar", "ABSENCE", null, null, "#78350F", false, false),
            new Def("DIL", "Diligência", "ABSENCE", null, null, "#0369A1", false, false),
            new Def("LIC", "Licença de Estudos", "ABSENCE", null, null, "#0F766E", false, false));

    private final ShiftTypeRepository types;
    private final Clock clock;

    DefaultShiftTypes(ShiftTypeRepository types, Clock clock) {
        this.types = types;
        this.clock = clock;
    }

    /** Síncrono, na mesma transação da criação do posto. */
    @EventListener
    void on(PostoCreated event) {
        int pos = 0;
        for (Def d : DEFAULTS) {
            boolean allDay = !d.kind().equals("WORK");
            UUID id = Ids.newId();
            types.insert(new ShiftTypeInfo(id, event.postoId(), d.code(), d.name(), d.kind(), allDay,
                    d.start() == null ? null : LocalTime.parse(d.start()), d.minutes(), d.color(), d.swappable(), d.accumulable()),
                    pos++, clock.instant());
        }
    }
}
