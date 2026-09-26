package pt.turnos.scheduling.internal;

import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import pt.turnos.identity.CurrentUser;
import pt.turnos.scheduling.ShiftInfo;
import pt.turnos.scheduling.ShiftTypeInfo;
import pt.turnos.scheduling.Violation;

@RestController
@RequestMapping("/api/v1")
class SchedulingController {

    record PaintRequest(UUID shiftTypeId, @NotEmpty List<LocalDate> dates, LocalTime start, Integer durationMinutes) {
    }

    record AddRequest(@NotNull UUID shiftTypeId, @NotNull LocalDate date, LocalTime start, Integer durationMinutes,
                      @Size(max = 1000) String notes) {
    }

    record NotesRequest(int version, @Size(max = 1000) String notes) {
    }

    record ShiftDto(UUID id, UUID userId, LocalDate date, UUID shiftTypeId, String code, String name, String kind, String color,
                    boolean allDay, LocalTime start, Integer durationMinutes, Instant startsAt, Instant endsAt, String notes,
                    String source, int version) {
        static ShiftDto of(ShiftInfo s) {
            return new ShiftDto(s.id(), s.userId(), s.date(), s.type().id(), s.type().code(), s.type().name(), s.type().kind(),
                    s.type().color(), s.allDay(), s.localStart(), s.durationMinutes(), s.startsAt(), s.endsAt(), s.notes(),
                    s.source(), s.version());
        }
    }

    record WriteResponse(List<ShiftDto> shifts, List<Map<String, Object>> warnings) {
        static WriteResponse of(SchedulingService.Written w) {
            return new WriteResponse(w.shifts().stream().map(ShiftDto::of).toList(), w.warnings().stream().map(Violation::toMap).toList());
        }
    }

    private final SchedulingService service;

    SchedulingController(SchedulingService service) {
        this.service = service;
    }

    @GetMapping("/postos/{postoId}/shift-types")
    List<ShiftTypeInfo> types(CurrentUser me, @PathVariable UUID postoId) {
        return service.types(me, postoId);
    }

    @GetMapping("/me/shifts")
    List<ShiftDto> mine(CurrentUser me, @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate from,
                        @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate to) {
        return service.mine(me, from, to).stream().map(ShiftDto::of).toList();
    }

    @PutMapping("/me/shifts/paint")
    WriteResponse paint(CurrentUser me, @Valid @RequestBody PaintRequest req) {
        return WriteResponse.of(service.paint(me, req.shiftTypeId(), req.dates(), req.start(), req.durationMinutes()));
    }

    @PostMapping("/me/shifts")
    @ResponseStatus(HttpStatus.CREATED)
    WriteResponse add(CurrentUser me, @Valid @RequestBody AddRequest req) {
        return WriteResponse.of(service.add(me, req.shiftTypeId(), req.date(), req.start(), req.durationMinutes(), req.notes()));
    }

    @PatchMapping("/shifts/{id}")
    ShiftDto notes(CurrentUser me, @PathVariable UUID id, @Valid @RequestBody NotesRequest req) {
        return ShiftDto.of(service.updateNotes(me, id, req.version(), req.notes()));
    }

    @DeleteMapping("/shifts/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    void delete(CurrentUser me, @PathVariable UUID id) {
        service.delete(me, id);
    }

    @GetMapping("/users/{userId}/shifts")
    List<ShiftDto> ofUser(CurrentUser me, @PathVariable UUID userId,
                          @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate from,
                          @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate to) {
        return service.ofUser(me, userId, from, to).stream().map(ShiftDto::of).toList();
    }

    /** Escala do posto; com {@code groupId}, só a do grupo de folgas. */
    @GetMapping("/postos/{postoId}/shifts")
    List<ShiftDto> ofPosto(CurrentUser me, @PathVariable UUID postoId, @RequestParam(required = false) UUID groupId,
                           @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate from,
                           @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate to) {
        return service.ofPosto(me, postoId, groupId, from, to).stream().map(ShiftDto::of).toList();
    }
}
