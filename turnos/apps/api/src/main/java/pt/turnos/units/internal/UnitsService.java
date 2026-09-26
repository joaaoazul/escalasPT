package pt.turnos.units.internal;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Clock;
import java.time.DateTimeException;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import pt.turnos.audit.AuditLog;
import pt.turnos.identity.CurrentUser;
import pt.turnos.identity.UserDirectory;
import pt.turnos.identity.UserSummary;
import pt.turnos.shared.ApiException;
import pt.turnos.shared.Ids;
import pt.turnos.units.MemberLeft;
import pt.turnos.units.Membership;
import pt.turnos.units.PostoCreated;
import pt.turnos.units.PostoInfo;

@Service
class UnitsService {

    static final Duration INVITE_TTL = Duration.ofDays(7);
    private static final String CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
    private static final SecureRandom RANDOM = new SecureRandom();

    record CreatedInvite(UUID id, String token, Instant expiresAt) {
    }

    private final UnitsRepository repo;
    private final UserDirectory users;
    private final ApplicationEventPublisher events;
    private final AuditLog audit;
    private final Clock clock;

    UnitsService(UnitsRepository repo, UserDirectory users, ApplicationEventPublisher events, AuditLog audit, Clock clock) {
        this.repo = repo;
        this.users = users;
        this.events = events;
        this.audit = audit;
        this.clock = clock;
    }

    // ── postos e grupos (administração) ──

    @Transactional
    PostoInfo createPosto(CurrentUser me, String name, String location, String zone) {
        requireAdmin(me);
        ZoneId zoneId;
        try {
            zoneId = ZoneId.of(zone == null || zone.isBlank() ? "Europe/Lisbon" : zone);
        } catch (DateTimeException e) {
            throw ApiException.invalid("invalid-time-zone", "Fuso horário desconhecido: " + zone);
        }
        UUID id = Ids.newId();
        repo.insertPosto(id, name.trim(), location.trim(), zoneId.getId(), clock.instant());
        events.publishEvent(new PostoCreated(id));
        audit.record(me.id(), "posto.created", "posto", id, Map.of("name", name));
        return repo.posto(id).orElseThrow();
    }

    @Transactional
    UnitsRepository.Group createGroup(CurrentUser me, UUID postoId, String name) {
        requireAdmin(me);
        repo.posto(postoId).orElseThrow(() -> ApiException.notFound("Posto"));
        UUID id = Ids.newId();
        repo.insertGroup(id, postoId, name.trim(), clock.instant());
        audit.record(me.id(), "group.created", "folga_group", id, Map.of("name", name));
        return repo.group(id).orElseThrow();
    }

    /** O posto é visível aos seus militares e ao administrador. */
    PostoInfo readablePosto(CurrentUser me, UUID postoId) {
        PostoInfo p = repo.posto(postoId).orElseThrow(() -> ApiException.notFound("Posto"));
        if (!me.admin() && repo.membershipOf(me.id()).filter(m -> m.postoId().equals(postoId)).isEmpty()) {
            throw ApiException.notFound("Posto");
        }
        return p;
    }

    // ── convites (comandante de grupo) ──

    @Transactional
    CreatedInvite invite(CurrentUser me, UUID groupId, String email, String name, String rank, String role) {
        UnitsRepository.Group g = repo.group(groupId).orElseThrow(() -> ApiException.notFound("Grupo"));
        requireCommanderOrAdmin(me, g);
        String r = role == null ? "MEMBER" : role;
        if (!r.equals("MEMBER") && !r.equals("COMMANDER")) {
            throw ApiException.invalid("invalid-role", "Papel inválido");
        }
        if (r.equals("COMMANDER") && !me.admin()) {
            throw ApiException.forbidden("Só o administrador nomeia o comandante de grupo");
        }
        String token = newToken();
        UUID id = Ids.newId();
        Instant now = clock.instant();
        Instant expires = now.plus(INVITE_TTL);
        repo.insertInvite(id, groupId, hash(token), normalizeEmail(email), blank(name), blank(rank), r, expires, me.id(), now);
        audit.record(me.id(), "invite.created", "group_invite", id, Map.of("groupId", groupId.toString(), "role", r));
        return new CreatedInvite(id, token, expires);
    }

    java.util.List<UnitsRepository.Invite> invites(CurrentUser me, UUID groupId) {
        UnitsRepository.Group g = repo.group(groupId).orElseThrow(() -> ApiException.notFound("Grupo"));
        requireCommanderOrAdmin(me, g);
        return repo.invitesOfGroup(groupId);
    }

    @Transactional
    void revokeInvite(CurrentUser me, UUID groupId, UUID inviteId) {
        UnitsRepository.Group g = repo.group(groupId).orElseThrow(() -> ApiException.notFound("Grupo"));
        requireCommanderOrAdmin(me, g);
        if (!repo.revokeInvite(inviteId, groupId, clock.instant())) {
            throw ApiException.notFound("Convite");
        }
        audit.record(me.id(), "invite.revoked", "group_invite", inviteId, null);
    }

    record InvitePreview(UUID groupId, String groupName, String postoName, String invitedBy, Instant expiresAt, String status) {
    }

    InvitePreview preview(String token) {
        UnitsRepository.Invite inv = repo.inviteByHash(hash(token)).orElseThrow(() -> ApiException.notFound("Convite"));
        UnitsRepository.Group g = repo.group(inv.groupId()).orElseThrow();
        PostoInfo p = repo.posto(g.postoId()).orElseThrow();
        String by = inv.createdBy() == null ? null : users.find(inv.createdBy()).map(UserSummary::displayName).orElse(null);
        return new InvitePreview(g.id(), g.name(), p.name(), by, inv.expiresAt(), status(inv));
    }

    @Transactional
    Membership accept(CurrentUser me, String token) {
        Instant now = clock.instant();
        UnitsRepository.Invite inv = repo.inviteByHash(hash(token)).orElseThrow(() -> ApiException.notFound("Convite"));
        String status = status(inv);
        if (!status.equals("PENDING")) {
            throw ApiException.invalid("invite-" + status.toLowerCase(Locale.ROOT), switch (status) {
                case "ACCEPTED" -> "Este convite já foi usado";
                case "REVOKED" -> "Este convite foi revogado";
                default -> "Este convite expirou";
            });
        }
        UserSummary user = users.find(me.id()).orElseThrow();
        if (inv.email() != null && !inv.email().equalsIgnoreCase(user.email())) {
            throw ApiException.forbidden("Este convite é para outro email");
        }
        if (repo.membershipOf(me.id()).isPresent()) {
            throw ApiException.conflict("already-member", "Já pertences a um grupo de folgas. Sai primeiro desse grupo.");
        }
        if (!repo.consumeInvite(inv.id(), me.id(), now)) {
            throw ApiException.conflict("invite-used", "Este convite já foi usado");
        }
        if (inv.role().equals("COMMANDER")) {
            repo.membershipOfGroupCommander(inv.groupId()).ifPresent(old -> repo.setRole(inv.groupId(), old, "MEMBER"));
        }
        repo.addMember(inv.groupId(), me.id(), inv.role(), now);
        audit.record(me.id(), "member.joined", "folga_group", inv.groupId(), Map.of("inviteId", inv.id().toString()));
        return repo.membershipOf(me.id()).orElseThrow();
    }

    @Transactional
    void removeMember(CurrentUser me, UUID groupId, UUID userId) {
        UnitsRepository.Group g = repo.group(groupId).orElseThrow(() -> ApiException.notFound("Grupo"));
        boolean self = me.id().equals(userId);
        if (!self) {
            requireCommanderOrAdmin(me, g);
        }
        Membership m = repo.membershipOf(userId).filter(x -> x.groupId().equals(groupId))
                .orElseThrow(() -> ApiException.notFound("Militar"));
        if (m.commander() && !me.admin()) {
            throw ApiException.invalid("commander-must-transfer", "O comandante de grupo tem de passar o comando antes de sair");
        }
        repo.removeMember(groupId, userId);
        events.publishEvent(new MemberLeft(userId, g.postoId(), groupId, me.id()));
        audit.record(me.id(), self ? "member.left" : "member.removed", "folga_group", groupId, Map.of("userId", userId.toString()));
    }

    @Transactional
    void transferCommand(CurrentUser me, UUID groupId, UUID newCommander) {
        UnitsRepository.Group g = repo.group(groupId).orElseThrow(() -> ApiException.notFound("Grupo"));
        requireCommanderOrAdmin(me, g);
        repo.membershipOf(newCommander).filter(x -> x.groupId().equals(groupId))
                .orElseThrow(() -> ApiException.invalid("not-a-member", "Esse militar não pertence ao grupo"));
        repo.membershipOfGroupCommander(groupId).ifPresent(old -> repo.setRole(groupId, old, "MEMBER"));
        repo.setRole(groupId, newCommander, "COMMANDER");
        audit.record(me.id(), "group.command-transferred", "folga_group", groupId, Map.of("to", newCommander.toString()));
    }

    // ── auxiliares ──

    private void requireAdmin(CurrentUser me) {
        if (!me.admin()) {
            throw ApiException.forbidden("Operação reservada ao administrador");
        }
    }

    private void requireCommanderOrAdmin(CurrentUser me, UnitsRepository.Group g) {
        if (me.admin()) {
            return;
        }
        boolean commander = repo.membershipOf(me.id()).filter(m -> m.groupId().equals(g.id()) && m.commander()).isPresent();
        if (!commander) {
            throw ApiException.forbidden("Só o comandante de grupo pode fazer isto");
        }
    }

    String status(UnitsRepository.Invite inv) {
        if (inv.acceptedAt() != null) {
            return "ACCEPTED";
        }
        if (inv.revokedAt() != null) {
            return "REVOKED";
        }
        return inv.expiresAt().isAfter(clock.instant()) ? "PENDING" : "EXPIRED";
    }

    /** 20 caracteres Crockford Base32 (100 bits), mostrado como XXXXX-XXXXX-XXXXX-XXXXX. */
    static String newToken() {
        StringBuilder sb = new StringBuilder(23);
        for (int i = 0; i < 20; i++) {
            if (i > 0 && i % 5 == 0) {
                sb.append('-');
            }
            sb.append(CROCKFORD.charAt(RANDOM.nextInt(32)));
        }
        return sb.toString();
    }

    static byte[] hash(String token) {
        String canonical = token.replace("-", "").trim().toUpperCase(Locale.ROOT);
        try {
            return MessageDigest.getInstance("SHA-256").digest(canonical.getBytes(StandardCharsets.UTF_8));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    private static String normalizeEmail(String email) {
        return email == null || email.isBlank() ? null : email.trim().toLowerCase(Locale.ROOT);
    }

    private static String blank(String s) {
        return s == null || s.isBlank() ? null : s.trim();
    }
}
