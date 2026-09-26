package pt.turnos.scheduling.internal;

import java.time.Clock;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.TreeSet;
import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import pt.turnos.audit.AuditLog;
import pt.turnos.identity.CurrentUser;
import pt.turnos.scheduling.Scheduling;
import pt.turnos.scheduling.ShiftInfo;
import pt.turnos.scheduling.ShiftRules;
import pt.turnos.scheduling.ShiftTimes;
import pt.turnos.scheduling.ShiftTypeInfo;
import pt.turnos.scheduling.Violation;
import pt.turnos.shared.ApiException;
import pt.turnos.shared.Ids;
import pt.turnos.units.Membership;
import pt.turnos.units.PostoInfo;
import pt.turnos.units.Units;

@Service
class SchedulingService implements Scheduling {

    static final int MAX_PAINT_DAYS = 62;
    static final int MAX_POSTO_RANGE_DAYS = 62;
    static final int MAX_USER_RANGE_DAYS = 400;

    record Written(List<ShiftInfo> shifts, List<Violation> warnings) {
    }

    private final ShiftRepository shifts;
    private final ShiftTypeRepository types;
    private final Units units;
    private final AuditLog audit;
    private final Clock clock;

    SchedulingService(ShiftRepository shifts, ShiftTypeRepository types, Units units, AuditLog audit, Clock clock) {
        this.shifts = shifts;
        this.types = types;
        this.units = units;
        this.audit = audit;
        this.clock = clock;
    }

    // ── tipos ──

    List<ShiftTypeInfo> types(CurrentUser me, UUID postoId) {
        requirePostoAccess(me, postoId);
        return types.ofPosto(postoId);
    }

    // ── escrita ──

    /** Modo pincel: substitui o conteúdo dos dias pelo tipo escolhido ({@code typeId == null} limpa os dias). */
    @Transactional
    Written paint(CurrentUser me, UUID typeId, List<LocalDate> rawDates, LocalTime start, Integer duration) {
        Membership m = membership(me);
        Set<LocalDate> dates = new TreeSet<>(rawDates);
        if (dates.isEmpty() || dates.size() > MAX_PAINT_DAYS) {
            throw ApiException.invalid("invalid-dates", "Escolhe entre 1 e " + MAX_PAINT_DAYS + " dias");
        }
        ShiftTypeInfo type = typeId == null ? null : postoType(m, typeId);
        LocalDate first = ((TreeSet<LocalDate>) dates).first(), last = ((TreeSet<LocalDate>) dates).last();

        List<ShiftInfo> window = new ArrayList<>(shifts.ofUser(me.id(), first.minusDays(1), last.plusDays(1)));
        List<ShiftInfo> removed = window.stream().filter(s -> dates.contains(s.date())).toList();
        for (ShiftInfo s : removed) {
            if (shifts.hasActiveSwap(s.id())) {
                throw ApiException.invalid("shift-has-active-swap", "O serviço de " + s.date() + " tem um pedido de troca ativo");
            }
        }
        window.removeAll(removed);
        removed.forEach(s -> shifts.delete(s.id()));

        List<ShiftInfo> created = new ArrayList<>();
        List<Violation> violations = new ArrayList<>();
        if (type != null) {
            PostoInfo posto = units.posto(m.postoId()).orElseThrow();
            for (LocalDate d : dates) {
                ShiftInfo s = build(me.id(), posto, type, d, start, duration, null, "PAINT");
                violations.addAll(ShiftRules.check(window, s));
                window.add(s);
                created.add(s);
            }
        }
        failOnErrors(violations);
        created.forEach(s -> shifts.insert(s, clock.instant()));
        audit.record(me.id(), "shifts.painted", "user", me.id(),
                Map.of("type", type == null ? "—" : type.code(), "dates", dates.stream().map(LocalDate::toString).toList()));
        return new Written(created, warnings(violations));
    }

    /** Acrescenta um serviço sem apagar os do dia (ex.: um gratificado num dia de serviço normal). */
    @Transactional
    Written add(CurrentUser me, UUID typeId, LocalDate date, LocalTime start, Integer duration, String notes) {
        Membership m = membership(me);
        ShiftTypeInfo type = postoType(m, typeId);
        PostoInfo posto = units.posto(m.postoId()).orElseThrow();
        ShiftInfo s = build(me.id(), posto, type, date, start, duration, notes, "MANUAL");
        List<Violation> violations = ShiftRules.check(shifts.ofUser(me.id(), date.minusDays(1), date.plusDays(1)), s);
        failOnErrors(violations);
        shifts.insert(s, clock.instant());
        audit.record(me.id(), "shift.created", "shift", s.id(), Map.of("type", type.code(), "date", date.toString()));
        return new Written(List.of(s), warnings(violations));
    }

    @Transactional
    ShiftInfo updateNotes(CurrentUser me, UUID id, int version, String notes) {
        ShiftInfo s = owned(me, id);
        if (shifts.updateNotes(id, version, notes, clock.instant()) == 0) {
            throw ApiException.conflict("version-conflict", "O serviço foi alterado entretanto. Atualiza e tenta de novo.");
        }
        audit.record(me.id(), "shift.updated", "shift", s.id(), null);
        return shifts.find(id).orElseThrow();
    }

    @Transactional
    void delete(CurrentUser me, UUID id) {
        ShiftInfo s = owned(me, id);
        if (shifts.hasActiveSwap(id)) {
            throw ApiException.invalid("shift-has-active-swap", "Este serviço tem um pedido de troca ativo");
        }
        shifts.delete(id);
        audit.record(me.id(), "shift.deleted", "shift", s.id(), Map.of("type", s.type().code(), "date", s.date().toString()));
    }

    // ── leitura ──

    List<ShiftInfo> mine(CurrentUser me, LocalDate from, LocalDate to) {
        checkRange(from, to, MAX_USER_RANGE_DAYS);
        return shifts.ofUser(me.id(), from, to);
    }

    /** Escala de um camarada: só para militares do mesmo posto. */
    List<ShiftInfo> ofUser(CurrentUser me, UUID userId, LocalDate from, LocalDate to) {
        checkRange(from, to, MAX_USER_RANGE_DAYS);
        Membership other = units.membershipOf(userId).orElseThrow(() -> ApiException.notFound("Militar"));
        requirePostoAccess(me, other.postoId());
        return shifts.ofUser(userId, from, to);
    }

    /** Escala do posto (ou de um grupo de folgas do posto). */
    List<ShiftInfo> ofPosto(CurrentUser me, UUID postoId, UUID groupId, LocalDate from, LocalDate to) {
        checkRange(from, to, MAX_POSTO_RANGE_DAYS);
        requirePostoAccess(me, postoId);
        List<ShiftInfo> all = shifts.ofPosto(postoId, from, to);
        if (groupId == null) {
            return all;
        }
        Set<UUID> members = new HashSet<>();
        units.membersOfPosto(postoId).stream().filter(x -> x.groupId().equals(groupId)).forEach(x -> members.add(x.userId()));
        return all.stream().filter(s -> members.contains(s.userId())).toList();
    }

    // ── API pública para as trocas ──

    @Override
    public Optional<ShiftInfo> find(UUID shiftId) {
        return shifts.find(shiftId);
    }

    @Override
    public List<ShiftInfo> lockForUpdate(List<UUID> ids) {
        return shifts.lockForUpdate(ids);
    }

    @Override
    public List<ShiftInfo> ofUser(UUID userId, LocalDate from, LocalDate toInclusive) {
        return shifts.ofUser(userId, from, toInclusive);
    }

    @Override
    public void swapOwners(ShiftInfo a, ShiftInfo b, UUID swapRequestId) {
        shifts.deferConstraints();
        shifts.setOwner(a.id(), b.userId(), swapRequestId, clock.instant());
        shifts.setOwner(b.id(), a.userId(), swapRequestId, clock.instant());
    }

    // ── auxiliares ──

    private ShiftInfo build(UUID userId, PostoInfo posto, ShiftTypeInfo type, LocalDate date, LocalTime start, Integer duration,
                            String notes, String source) {
        LocalTime st = null;
        Integer dur = null;
        if (!type.allDay()) {
            if (type.variableHours()) {
                if (start == null || duration == null || duration < 1 || duration > 1440) {
                    throw ApiException.invalid("hours-required", type.name() + " precisa de hora de início e duração");
                }
                st = start;
                dur = duration;
            } else {
                st = type.startTime();
                dur = type.durationMinutes();
            }
        }
        ShiftTimes.Span span = ShiftTimes.resolve(date, st, dur, type.allDay(), posto.zone());
        return new ShiftInfo(Ids.newId(), userId, posto.id(), type, date, st, dur, span.startsAt(), span.endsAt(), notes, source, 0);
    }

    private Membership membership(CurrentUser me) {
        return units.membershipOf(me.id())
                .orElseThrow(() -> ApiException.invalid("no-posto", "Ainda não pertences a um grupo de folgas"));
    }

    private ShiftTypeInfo postoType(Membership m, UUID typeId) {
        return types.find(typeId).filter(t -> t.postoId().equals(m.postoId()))
                .orElseThrow(() -> ApiException.notFound("Tipo de serviço"));
    }

    private ShiftInfo owned(CurrentUser me, UUID id) {
        return shifts.find(id).filter(s -> s.userId().equals(me.id())).orElseThrow(() -> ApiException.notFound("Serviço"));
    }

    private void requirePostoAccess(CurrentUser me, UUID postoId) {
        if (me.admin()) {
            return;
        }
        if (units.membershipOf(me.id()).filter(x -> x.postoId().equals(postoId)).isEmpty()) {
            throw ApiException.notFound("Posto");
        }
    }

    private static void checkRange(LocalDate from, LocalDate to, int maxDays) {
        if (from == null || to == null || to.isBefore(from) || ChronoUnit.DAYS.between(from, to) >= maxDays) {
            throw ApiException.invalid("invalid-range", "Intervalo de datas inválido (máximo " + maxDays + " dias)");
        }
    }

    private static void failOnErrors(List<Violation> violations) {
        List<Violation> errors = violations.stream().filter(Violation::error).toList();
        if (!errors.isEmpty()) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT, "shift-conflict",
                    errors.size() == 1 ? errors.getFirst().message() : errors.size() + " conflitos",
                    errors.stream().map(Violation::toMap).toList());
        }
    }

    private static List<Violation> warnings(List<Violation> violations) {
        return violations.stream().filter(v -> !v.error()).toList();
    }
}
