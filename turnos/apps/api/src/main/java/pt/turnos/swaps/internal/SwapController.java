package pt.turnos.swaps.internal;

import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalTime;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import pt.turnos.identity.CurrentUser;
import pt.turnos.identity.UserDirectory;
import pt.turnos.identity.UserSummary;
import pt.turnos.scheduling.Scheduling;
import pt.turnos.scheduling.ShiftInfo;
import pt.turnos.scheduling.Violation;

@RestController
@RequestMapping("/api/v1")
class SwapController {

    record CreateSwap(@NotNull UUID shiftId, @NotNull UUID targetShiftId, @Size(max = 280) String message) {
    }

    record Note(@Size(max = 280) String message) {
    }

    record Person(UUID userId, String displayName) {
    }

    record ShiftRef(UUID id, LocalDate date, String code, String name, String color, LocalTime start, Integer durationMinutes) {
    }

    record SwapDto(UUID id, String status, Person requester, ShiftRef requesterShift, Person target, ShiftRef targetShift,
                   String message, String holdMessage, String declineReason, Instant createdAt, Instant heldAt,
                   Instant respondedAt, Instant expiresAt, String documentReference, List<Map<String, Object>> warnings) {
    }

    private final SwapService service;
    private final SwapRepository repo;
    private final Scheduling scheduling;
    private final UserDirectory users;

    SwapController(SwapService service, SwapRepository repo, Scheduling scheduling, UserDirectory users) {
        this.service = service;
        this.repo = repo;
        this.scheduling = scheduling;
        this.users = users;
    }

    @PostMapping("/swaps")
    @ResponseStatus(HttpStatus.CREATED)
    SwapDto create(CurrentUser me, @Valid @RequestBody CreateSwap req) {
        SwapService.Created c = service.request(me, req.shiftId(), req.targetShiftId(), req.message());
        return dto(c.swap(), c.warnings());
    }

    @GetMapping("/me/swaps")
    List<SwapDto> list(CurrentUser me, @RequestParam(defaultValue = "received") @Pattern(regexp = "received|sent|history") String box) {
        return service.list(me, box).stream().map(s -> dto(s, List.of())).toList();
    }

    @GetMapping("/swaps/{id}")
    SwapDto get(CurrentUser me, @PathVariable UUID id) {
        return dto(service.get(me, id), List.of());
    }

    @PostMapping("/swaps/{id}/accept")
    SwapDto accept(CurrentUser me, @PathVariable UUID id) {
        return dto(service.accept(me, id), List.of());
    }

    @PostMapping("/swaps/{id}/hold")
    SwapDto hold(CurrentUser me, @PathVariable UUID id, @Valid @RequestBody(required = false) Note note) {
        return dto(service.hold(me, id, note == null ? null : note.message()), List.of());
    }

    @PostMapping("/swaps/{id}/decline")
    SwapDto decline(CurrentUser me, @PathVariable UUID id, @Valid @RequestBody(required = false) Note note) {
        return dto(service.decline(me, id, note == null ? null : note.message()), List.of());
    }

    @PostMapping("/swaps/{id}/cancel")
    SwapDto cancel(CurrentUser me, @PathVariable UUID id) {
        return dto(service.cancel(me, id), List.of());
    }

    @GetMapping("/swaps/{id}/document.pdf")
    ResponseEntity<byte[]> document(CurrentUser me, @PathVariable UUID id) {
        SwapRepository.Document d = service.document(me, id);
        return ResponseEntity.ok()
                .contentType(MediaType.APPLICATION_PDF)
                .header(HttpHeaders.CONTENT_DISPOSITION,
                        ContentDisposition.attachment().filename("troca-" + d.reference() + ".pdf").build().toString())
                .header("X-Content-SHA256", HexFormat.of().formatHex(d.sha256()))
                .body(d.pdf());
    }

    private SwapDto dto(SwapRow s, List<Violation> warnings) {
        Map<UUID, UserSummary> people = new java.util.HashMap<>();
        users.findAll(List.of(s.requesterId(), s.targetId())).forEach(u -> people.put(u.id(), u));
        return new SwapDto(s.id(), s.status(), person(people.get(s.requesterId())), shift(s.requesterShiftId()),
                person(people.get(s.targetId())), shift(s.targetShiftId()), s.message(), s.holdMessage(), s.declineReason(),
                s.createdAt(), s.heldAt(), s.respondedAt(), s.expiresAt(), repo.documentReference(s.id()).orElse(null),
                warnings.stream().map(Violation::toMap).toList());
    }

    private static Person person(UserSummary u) {
        return u == null ? null : new Person(u.id(), u.displayName());
    }

    private ShiftRef shift(UUID id) {
        return scheduling.find(id).map((ShiftInfo s) -> new ShiftRef(s.id(), s.date(), s.type().code(), s.type().name(),
                s.type().color(), s.localStart(), s.durationMinutes())).orElse(null);
    }
}
