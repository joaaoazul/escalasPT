package pt.turnos.swaps.internal;

import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.context.event.EventListener;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import pt.turnos.audit.AuditLog;
import pt.turnos.identity.CurrentUser;
import pt.turnos.identity.UserDirectory;
import pt.turnos.identity.UserSummary;
import pt.turnos.scheduling.Scheduling;
import pt.turnos.scheduling.ShiftInfo;
import pt.turnos.scheduling.ShiftRules;
import pt.turnos.scheduling.Violation;
import pt.turnos.shared.ApiException;
import pt.turnos.shared.Ids;
import pt.turnos.swaps.SwapEvent;
import pt.turnos.units.MemberLeft;
import pt.turnos.units.Membership;
import pt.turnos.units.PostoInfo;
import pt.turnos.units.Units;
import tools.jackson.databind.json.JsonMapper;

/**
 * Trocas de serviço entre militares do mesmo posto, sem autorização do comandante (doc 09).
 * PENDENTE → EM_ESPERA → ACEITE | RECUSADA | CANCELADA | EXPIRADA. Na aceitação, os serviços trocam de dono
 * e o documento oficial é emitido na mesma transação.
 */
@Service
class SwapService {

    private static final Logger log = LoggerFactory.getLogger(SwapService.class);
    private static final DateTimeFormatter DATE = DateTimeFormatter.ofPattern("dd/MM/yyyy");
    private static final DateTimeFormatter HM = DateTimeFormatter.ofPattern("HH:mm");
    private static final DateTimeFormatter STAMP = DateTimeFormatter.ofPattern("dd/MM/yyyy 'às' HH:mm");
    private static final SecureRandom RANDOM = new SecureRandom();

    record Created(SwapRow swap, List<Violation> warnings) {
    }

    private final SwapRepository swaps;
    private final Scheduling scheduling;
    private final Units units;
    private final UserDirectory users;
    private final AuditLog audit;
    private final JsonMapper json;
    private final Clock clock;
    private final ApplicationEventPublisher events;

    SwapService(SwapRepository swaps, Scheduling scheduling, Units units, UserDirectory users, AuditLog audit, JsonMapper json,
                Clock clock, ApplicationEventPublisher events) {
        this.events = events;
        this.swaps = swaps;
        this.scheduling = scheduling;
        this.units = units;
        this.users = users;
        this.audit = audit;
        this.json = json;
        this.clock = clock;
    }

    // ── pedir ──

    @Transactional
    Created request(CurrentUser me, UUID myShiftId, UUID theirShiftId, String message) {
        Membership mine = units.membershipOf(me.id())
                .orElseThrow(() -> ApiException.invalid("no-posto", "Ainda não pertences a um grupo de folgas"));
        ShiftInfo a = scheduling.find(myShiftId).filter(s -> s.userId().equals(me.id()))
                .orElseThrow(() -> ApiException.notFound("Serviço"));
        ShiftInfo b = scheduling.find(theirShiftId).orElseThrow(() -> ApiException.notFound("Serviço do camarada"));
        if (b.userId().equals(me.id())) {
            throw ApiException.invalid("self-swap", "Não podes trocar um serviço contigo próprio");
        }
        Membership theirs = units.membershipOf(b.userId()).orElseThrow(() -> ApiException.notFound("Serviço do camarada"));
        if (!theirs.postoId().equals(mine.postoId()) || !a.postoId().equals(mine.postoId()) || !b.postoId().equals(mine.postoId())) {
            throw ApiException.notFound("Serviço do camarada");
        }
        PostoInfo posto = units.posto(mine.postoId()).orElseThrow();
        List<Violation> violations = validate(a, b, posto.zone());
        failOnErrors(violations);
        if (swaps.shiftHasActive(a.id()) || swaps.shiftHasActive(b.id())) {
            throw ApiException.conflict("swap-already-active", "Um destes serviços já tem um pedido de troca ativo");
        }

        LocalDate earliest = a.date().isBefore(b.date()) ? a.date() : b.date();
        Instant now = clock.instant();
        SwapRow row = new SwapRow(Ids.newId(), posto.id(), me.id(), a.id(), a.version(), b.userId(), b.id(), b.version(), "PENDENTE",
                blank(message), null, null, null, null, earliest.atStartOfDay(posto.zone()).toInstant(), now, 0);
        swaps.insert(row, now);
        audit.record(me.id(), "swap.requested", "swap_request", row.id(),
                Map.of("requesterShift", a.id().toString(), "targetShift", b.id().toString()));
        publish(SwapEvent.Type.REQUESTED, row, row.message());
        return new Created(swaps.find(row.id()).orElseThrow(), violations.stream().filter(v -> !v.error()).toList());
    }

    // ── responder (camarada) ──

    @Transactional(noRollbackFor = ApiException.class)
    SwapRow accept(CurrentUser me, UUID id) {
        Instant now = clock.instant();
        SwapRow s = lockActiveAsTarget(me, id, now);
        List<ShiftInfo> locked = scheduling.lockForUpdate(List.of(s.requesterShiftId(), s.targetShiftId()));
        ShiftInfo a = locked.stream().filter(x -> x.id().equals(s.requesterShiftId())).findFirst().orElse(null);
        ShiftInfo b = locked.stream().filter(x -> x.id().equals(s.targetShiftId())).findFirst().orElse(null);
        if (a == null || b == null || a.version() != s.requesterShiftVersion() || b.version() != s.targetShiftVersion()
                || !a.userId().equals(s.requesterId()) || !b.userId().equals(s.targetId())) {
            swaps.close(s.id(), "CANCELADA", "Serviço alterado depois do pedido", now);
            throw ApiException.conflict("shift-changed", "Um dos serviços foi alterado depois do pedido. O pedido foi cancelado.");
        }
        PostoInfo posto = units.posto(s.postoId()).orElseThrow();
        failOnErrors(validate(a, b, posto.zone()));

        scheduling.swapOwners(a, b, s.id());
        swaps.close(s.id(), "ACEITE", null, now);
        swaps.cancelOthersInvolving(s.id(), a.id(), b.id(), now);
        issueDocument(s, a, b, posto, now);
        audit.record(me.id(), "swap.accepted", "swap_request", s.id(), null);
        publish(SwapEvent.Type.ACCEPTED, s, null);
        return swaps.find(id).orElseThrow();
    }

    @Transactional(noRollbackFor = ApiException.class)
    SwapRow hold(CurrentUser me, UUID id, String message) {
        Instant now = clock.instant();
        SwapRow s = lockActiveAsTarget(me, id, now);
        swaps.hold(s.id(), blank(message), now);
        audit.record(me.id(), "swap.held", "swap_request", s.id(), null);
        publish(SwapEvent.Type.HELD, s, blank(message));
        return swaps.find(id).orElseThrow();
    }

    @Transactional(noRollbackFor = ApiException.class)
    SwapRow decline(CurrentUser me, UUID id, String reason) {
        Instant now = clock.instant();
        SwapRow s = lockActiveAsTarget(me, id, now);
        swaps.close(s.id(), "RECUSADA", blank(reason), now);
        audit.record(me.id(), "swap.declined", "swap_request", s.id(), null);
        publish(SwapEvent.Type.DECLINED, s, blank(reason));
        return swaps.find(id).orElseThrow();
    }

    // ── cancelar (quem pediu) ──

    @Transactional
    SwapRow cancel(CurrentUser me, UUID id) {
        SwapRow s = swaps.lock(id).filter(x -> x.involves(me.id())).orElseThrow(() -> ApiException.notFound("Pedido de troca"));
        if (!s.requesterId().equals(me.id())) {
            throw ApiException.forbidden("Só quem pediu a troca a pode cancelar");
        }
        requireActive(s);
        swaps.close(s.id(), "CANCELADA", null, clock.instant());
        audit.record(me.id(), "swap.cancelled", "swap_request", s.id(), null);
        publish(SwapEvent.Type.CANCELLED, s, null);
        return swaps.find(id).orElseThrow();
    }

    // ── leitura ──

    SwapRow get(CurrentUser me, UUID id) {
        return swaps.find(id).filter(s -> s.involves(me.id())).orElseThrow(() -> ApiException.notFound("Pedido de troca"));
    }

    List<SwapRow> list(CurrentUser me, String box) {
        return swaps.ofUser(me.id(), box);
    }

    SwapRepository.Document document(CurrentUser me, UUID id) {
        get(me, id);
        return swaps.document(id).orElseThrow(() -> ApiException.notFound("Documento"));
    }

    // ── automático ──

    @Transactional
    int expire() {
        List<UUID> expired = swaps.expire(clock.instant());
        expired.forEach(id -> {
            audit.record(null, "swap.expired", "swap_request", id, null);
            swaps.find(id).ifPresent(s -> publish(SwapEvent.Type.EXPIRED, s, null));
        });
        if (!expired.isEmpty()) {
            log.info("{} pedidos de troca expiraram", expired.size());
        }
        return expired.size();
    }

    /** Quem sai do grupo de folgas (e do posto) deixa de poder trocar: os pedidos ativos caem. */
    @EventListener
    void on(MemberLeft event) {
        swaps.cancelActiveOf(event.userId(), clock.instant());
    }

    private void publish(SwapEvent.Type type, SwapRow s, String note) {
        String reqCode = scheduling.find(s.requesterShiftId()).map(x -> x.type().code()).orElse("?");
        ShiftInfo target = scheduling.find(s.targetShiftId()).orElse(null);
        LocalDate date = target == null ? null : target.date();
        String tgtCode = target == null ? "?" : target.type().code();
        events.publishEvent(new SwapEvent(type, s.id(), s.requesterId(), s.targetId(), date, reqCode, tgtCode, note));
    }

    // ── regras ──

    /** Regras 3, 4, 6 e 8 do doc 09 (as outras são verificadas por quem chama). */
    private List<Violation> validate(ShiftInfo a, ShiftInfo b, ZoneId zone) {
        if (!a.type().swappable() || !b.type().swappable()) {
            ShiftInfo abs = a.type().swappable() ? b : a;
            throw ApiException.invalid("type-not-swappable", "Não é possível trocar " + abs.type().name() + " (ausência)");
        }
        if (a.date().equals(b.date()) && a.type().id().equals(b.type().id())) {
            throw ApiException.invalid("same-service", "Não pode trocar com um militar que está no mesmo serviço, no mesmo dia");
        }
        LocalDate today = LocalDate.now(clock.withZone(zone));
        LocalDate earliest = a.date().isBefore(b.date()) ? a.date() : b.date();
        if (!earliest.isAfter(today)) {
            throw ApiException.invalid("too-late", "As trocas são pedidas até à véspera do serviço (Art. 34.º, n.º 2)");
        }
        // Como fica cada um depois da troca
        List<Violation> v = new ArrayList<>();
        v.addAll(afterSwap(a.userId(), a, b));
        v.addAll(afterSwap(b.userId(), b, a));
        return v;
    }

    private List<Violation> afterSwap(UUID owner, ShiftInfo gives, ShiftInfo receives) {
        List<ShiftInfo> keeps = scheduling.ofUser(owner, receives.date().minusDays(1), receives.date().plusDays(1)).stream()
                .filter(s -> !s.id().equals(gives.id())).toList();
        return ShiftRules.check(keeps, receives.ownedBy(owner));
    }

    private SwapRow lockActiveAsTarget(CurrentUser me, UUID id, Instant now) {
        SwapRow s = swaps.lock(id).filter(x -> x.involves(me.id())).orElseThrow(() -> ApiException.notFound("Pedido de troca"));
        if (!s.targetId().equals(me.id())) {
            throw ApiException.forbidden("Só o camarada a quem foi pedida a troca pode responder");
        }
        requireActive(s);
        if (!s.expiresAt().isAfter(now)) {
            swaps.close(s.id(), "EXPIRADA", null, now);
            throw ApiException.conflict("swap-expired", "O pedido expirou na véspera do serviço");
        }
        return s;
    }

    private static void requireActive(SwapRow s) {
        if (!s.active()) {
            throw ApiException.conflict("swap-invalid-state", "Este pedido já não está ativo (" + s.status() + ")");
        }
    }

    private static void failOnErrors(List<Violation> violations) {
        List<Violation> errors = violations.stream().filter(Violation::error).toList();
        if (!errors.isEmpty()) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT, "swap-conflict",
                    "A troca criaria conflitos: " + String.join("; ", errors.stream().map(Violation::message).toList()),
                    errors.stream().map(Violation::toMap).toList());
        }
    }

    // ── documento ──

    private void issueDocument(SwapRow s, ShiftInfo a, ShiftInfo b, PostoInfo posto, Instant now) {
        ZoneId z = posto.zone();
        UserSummary req = users.find(s.requesterId()).orElseThrow();
        UserSummary tgt = users.find(s.targetId()).orElseThrow();
        String reference = HexFormat.of().withUpperCase().formatHex(randomBytes(4));
        SwapForm.Data data = new SwapForm.Data(reference, posto.name(), posto.location(), LocalDate.ofInstant(now, z),
                req.displayName(), a.type().name(), DATE.format(a.date()), start(a, z), end(a, z),
                tgt.displayName(), b.type().name(), start(b, z), end(b, z),
                STAMP.format(s.createdAt().atZone(z)), STAMP.format(now.atZone(z)));
        byte[] pdf = SwapForm.render(data);
        Map<String, Object> snapshot = new LinkedHashMap<>();
        snapshot.put("form", data);
        snapshot.put("requesterShift", Map.of("id", a.id(), "date", a.date().toString(), "code", a.type().code()));
        snapshot.put("targetShift", Map.of("id", b.id(), "date", b.date().toString(), "code", b.type().code()));
        swaps.insertDocument(s.id(), reference, pdf, sha256(pdf), json.writeValueAsString(snapshot), now);
    }

    private static String start(ShiftInfo s, ZoneId z) {
        return s.allDay() ? "—" : HM.format(s.startsAt().atZone(z));
    }

    private static String end(ShiftInfo s, ZoneId z) {
        return s.allDay() ? "—" : HM.format(s.endsAt().atZone(z));
    }

    private static byte[] randomBytes(int n) {
        byte[] b = new byte[n];
        RANDOM.nextBytes(b);
        return b;
    }

    private static byte[] sha256(byte[] data) {
        try {
            return MessageDigest.getInstance("SHA-256").digest(data);
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    private static String blank(String s) {
        return s == null || s.isBlank() ? null : s.trim();
    }
}
