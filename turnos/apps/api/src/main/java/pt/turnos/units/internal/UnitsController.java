package pt.turnos.units.internal;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import pt.turnos.identity.CurrentUser;
import pt.turnos.identity.UserDirectory;
import pt.turnos.identity.UserSummary;
import pt.turnos.shared.ApiException;
import pt.turnos.units.Membership;
import pt.turnos.units.PostoInfo;

@RestController
@RequestMapping("/api/v1")
class UnitsController {

    record CreatePosto(@NotBlank @Size(max = 120) String name, @NotBlank @Size(max = 80) String location, String timeZone) {
    }

    record CreateGroup(@NotBlank @Size(max = 40) String name) {
    }

    record CreateInvite(@Email String email, @Size(max = 120) String name, @Size(max = 40) String rank, String role) {
    }

    record TransferCommand(@NotNull UUID userId) {
    }

    record MemberView(UUID userId, String displayName, String rank, String serviceNumber, boolean commander) {
    }

    record GroupView(UUID id, String name, List<MemberView> members) {
    }

    record PostoView(UUID id, String name, String location, String timeZone, List<GroupView> groups) {
    }

    record MembershipView(UUID postoId, String postoName, UUID groupId, String groupName, boolean commander) {
    }

    record InviteView(UUID id, String email, String name, String rank, String role, String status, Instant expiresAt,
                      Instant acceptedAt) {
    }

    private final UnitsService service;
    private final UnitsRepository repo;
    private final UserDirectory users;

    UnitsController(UnitsService service, UnitsRepository repo, UserDirectory users) {
        this.service = service;
        this.repo = repo;
        this.users = users;
    }

    @PostMapping("/postos")
    @ResponseStatus(HttpStatus.CREATED)
    PostoView createPosto(CurrentUser me, @Valid @RequestBody CreatePosto req) {
        PostoInfo p = service.createPosto(me, req.name(), req.location(), req.timeZone());
        return view(p);
    }

    /** Escala do posto: grupos de folgas e os seus militares. */
    @GetMapping("/postos/{postoId}")
    PostoView posto(CurrentUser me, @PathVariable UUID postoId) {
        return view(service.readablePosto(me, postoId));
    }

    @PostMapping("/postos/{postoId}/groups")
    @ResponseStatus(HttpStatus.CREATED)
    GroupView createGroup(CurrentUser me, @PathVariable UUID postoId, @Valid @RequestBody CreateGroup req) {
        UnitsRepository.Group g = service.createGroup(me, postoId, req.name());
        return new GroupView(g.id(), g.name(), List.of());
    }

    @GetMapping("/me/membership")
    MembershipView membership(CurrentUser me) {
        Membership m = repo.membershipOf(me.id()).orElseThrow(() -> ApiException.notFound("Grupo de folgas"));
        PostoInfo p = repo.posto(m.postoId()).orElseThrow();
        return new MembershipView(p.id(), p.name(), m.groupId(), m.groupName(), m.commander());
    }

    @PostMapping("/groups/{groupId}/invites")
    @ResponseStatus(HttpStatus.CREATED)
    Map<String, Object> invite(CurrentUser me, @PathVariable UUID groupId, @Valid @RequestBody CreateInvite req) {
        UnitsService.CreatedInvite inv = service.invite(me, groupId, req.email(), req.name(), req.rank(), req.role());
        // O código só é mostrado aqui, uma vez: na BD fica apenas o hash.
        return Map.of("id", inv.id(), "code", inv.token(), "expiresAt", inv.expiresAt());
    }

    @GetMapping("/groups/{groupId}/invites")
    List<InviteView> invites(CurrentUser me, @PathVariable UUID groupId) {
        return service.invites(me, groupId).stream().map(i -> new InviteView(i.id(), i.email(), i.inviteeName(), i.inviteeRank(),
                i.role(), service.status(i), i.expiresAt(), i.acceptedAt())).toList();
    }

    @DeleteMapping("/groups/{groupId}/invites/{inviteId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    void revoke(CurrentUser me, @PathVariable UUID groupId, @PathVariable UUID inviteId) {
        service.revokeInvite(me, groupId, inviteId);
    }

    @GetMapping("/invites/{code}")
    UnitsService.InvitePreview preview(@PathVariable String code) {
        return service.preview(code);
    }

    @PostMapping("/invites/{code}/accept")
    MembershipView accept(CurrentUser me, @PathVariable String code) {
        Membership m = service.accept(me, code);
        PostoInfo p = repo.posto(m.postoId()).orElseThrow();
        return new MembershipView(p.id(), p.name(), m.groupId(), m.groupName(), m.commander());
    }

    @DeleteMapping("/groups/{groupId}/members/{userId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    void removeMember(CurrentUser me, @PathVariable UUID groupId, @PathVariable UUID userId) {
        service.removeMember(me, groupId, userId);
    }

    @PostMapping("/groups/{groupId}/commander")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    void transfer(CurrentUser me, @PathVariable UUID groupId, @Valid @RequestBody TransferCommand req) {
        service.transferCommand(me, groupId, req.userId());
    }

    private PostoView view(PostoInfo p) {
        List<Membership> members = repo.membersOfPosto(p.id());
        Map<UUID, UserSummary> byId = users.findAll(members.stream().map(Membership::userId).toList()).stream()
                .collect(Collectors.toMap(UserSummary::id, u -> u));
        List<GroupView> groups = repo.groupsOfPosto(p.id()).stream().map(g -> new GroupView(g.id(), g.name(),
                members.stream().filter(m -> m.groupId().equals(g.id())).map(m -> {
                    UserSummary u = byId.get(m.userId());
                    return new MemberView(u.id(), u.displayName(), u.rank(), u.serviceNumber(), m.commander());
                }).toList())).toList();
        return new PostoView(p.id(), p.name(), p.location(), p.zone().getId(), groups);
    }
}
