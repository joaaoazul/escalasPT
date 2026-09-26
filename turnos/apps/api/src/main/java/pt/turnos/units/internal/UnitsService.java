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
import pt.turnos.identity.PasswordResets;
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
    static final int MAX_LINK_USES = 100;
    private static final String CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
    private static final SecureRandom RANDOM = new SecureRandom();

    record CreatedInvite(UUID id, String token, Instant expiresAt) {
    }

    private final UnitsRepository repo;
    private final UserDirectory users;
    private final PasswordResets resets;
    private final ApplicationEventPublisher events;
    private final AuditLog audit;
    private final Clock clock;

    UnitsService(UnitsRepository repo, UserDirectory users, PasswordResets resets, ApplicationEventPublisher events,
                 AuditLog audit, Clock clock) {
        this.repo = repo;
        this.users = users;
        this.resets = resets;
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

    /**
     * Convite individual ({@code maxUses} 1, pode indicar o email, o nome e o posto do militar) ou link do grupo
     * ({@code maxUses} &gt; 1, sem destinatário; criar um novo desativa o anterior).
     */
    @Transactional
    CreatedInvite invite(CurrentUser me, UUID groupId, String email, String name, String rank, String role, Integer maxUses) {
        UnitsRepository.Group g = repo.group(groupId).orElseThrow(() -> ApiException.notFound("Grupo"));
        requireCommanderOrAdmin(me, g);
        String r = role == null ? "MEMBER" : role;
        if (!r.equals("MEMBER") && !r.equals("COMMANDER")) {
            throw ApiException.invalid("invalid-role", "Papel inválido");
        }
        if (r.equals("COMMANDER") && !me.admin()) {
            throw ApiException.forbidden("Só o administrador nomeia o comandante de grupo");
        }
        int uses = maxUses == null ? 1 : maxUses;
        if (uses < 1 || uses > MAX_LINK_USES) {
            throw ApiException.invalid("invalid-max-uses", "O link do grupo serve entre 2 e " + MAX_LINK_USES + " militares");
        }
        boolean link = uses > 1;
        if (link && (r.equals("COMMANDER") || normalizeEmail(email) != null)) {
            throw ApiException.invalid("invalid-link", "O link do grupo é só para militares e não leva email");
        }
        String token = newToken();
        UUID id = Ids.newId();
        Instant now = clock.instant();
        Instant expires = now.plus(INVITE_TTL);
        if (link) {
            repo.revokeActiveLinks(groupId, now);
            name = null;
            rank = null;
        }
        repo.insertInvite(id, groupId, hash(token), normalizeEmail(email), blank(name), blank(rank), r, uses, expires, me.id(), now);
        audit.record(me.id(), link ? "invite-link.created" : "invite.created", "group_invite", id,
                Map.of("groupId", groupId.toString(), "role", r, "maxUses", uses));
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

    /** O que o convite mostra antes de se criar conta: o grupo e os dados que o comandante já preencheu. */
    record InvitePreview(UUID groupId, String groupName, String postoName, String invitedBy, Instant expiresAt, String status,
                         boolean link, boolean commander, String email, String name, String rank) {
    }

    InvitePreview preview(String token) {
        UnitsRepository.Invite inv = repo.inviteByHash(hash(token)).orElseThrow(() -> ApiException.notFound("Convite"));
        UnitsRepository.Group g = repo.group(inv.groupId()).orElseThrow();
        PostoInfo p = repo.posto(g.postoId()).orElseThrow();
        String by = inv.createdBy() == null ? null : users.find(inv.createdBy()).map(UserSummary::displayName).orElse(null);
        return new InvitePreview(g.id(), g.name(), p.name(), by, inv.expiresAt(), status(inv), inv.link(),
                inv.role().equals("COMMANDER"), inv.email(), inv.inviteeName(), inv.inviteeRank());
    }

    /** Validação do registo: o convite está válido e é para este email. */
    void checkForRegistration(String token, String email) {
        usable(token, email);
    }

    @Transactional
    Membership accept(CurrentUser me, String token) {
        return acceptFor(me.id(), token);
    }

    /**
     * Entra no grupo do convite. Quem já está noutro grupo do mesmo posto muda de grupo (as trocas e a escala
     * continuam, porque são do posto); o comandante tem de passar o comando antes.
     */
    @Transactional
    Membership acceptFor(UUID userId, String token) {
        Instant now = clock.instant();
        UserSummary user = users.find(userId).orElseThrow();
        UnitsRepository.Invite inv = usable(token, user.email());
        UnitsRepository.Group g = repo.group(inv.groupId()).orElseThrow();
        Membership current = repo.membershipOf(userId).orElse(null);
        if (current != null) {
            if (current.groupId().equals(g.id())) {
                throw ApiException.conflict("already-in-group", "Já pertences ao " + g.name());
            }
            if (!current.postoId().equals(g.postoId())) {
                throw ApiException.conflict("already-member", "Pertences a um grupo de outro posto. Sai primeiro desse grupo.");
            }
            if (current.commander()) {
                throw ApiException.invalid("commander-must-transfer", "Passa o comando do " + current.groupName() + " antes de mudar de grupo");
            }
        }
        if (!repo.consumeInvite(inv.id(), userId, now)) {
            throw ApiException.conflict("invite-used", "Este convite já foi usado");
        }
        if (inv.role().equals("COMMANDER")) {
            repo.membershipOfGroupCommander(inv.groupId()).ifPresent(old -> repo.setRole(inv.groupId(), old, "MEMBER"));
        }
        if (current == null) {
            repo.addMember(inv.groupId(), userId, inv.role(), now);
            audit.record(userId, "member.joined", "folga_group", inv.groupId(), Map.of("inviteId", inv.id().toString()));
        } else {
            repo.moveMember(userId, inv.groupId(), inv.role(), now);
            audit.record(userId, "member.moved", "folga_group", inv.groupId(),
                    Map.of("inviteId", inv.id().toString(), "from", current.groupId().toString()));
        }
        return repo.membershipOf(userId).orElseThrow();
    }

    private UnitsRepository.Invite usable(String token, String email) {
        UnitsRepository.Invite inv = repo.inviteByHash(hash(token)).orElseThrow(() -> ApiException.notFound("Convite"));
        String status = status(inv);
        if (!status.equals("PENDING")) {
            throw ApiException.invalid("invite-" + status.toLowerCase(Locale.ROOT), switch (status) {
                case "ACCEPTED" -> inv.link() ? "Este link já atingiu o limite de militares" : "Este convite já foi usado";
                case "REVOKED" -> "Este convite foi revogado";
                default -> "Este convite expirou";
            });
        }
        if (inv.email() != null && !inv.email().equalsIgnoreCase(email)) {
            throw ApiException.forbidden("Este convite é para outro email");
        }
        return inv;
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

    /** O comandante de grupo (ou o administrador) gera um código para o militar repor a palavra-passe. */
    @Transactional
    PasswordResets.Issued passwordReset(CurrentUser me, UUID groupId, UUID userId) {
        UnitsRepository.Group g = repo.group(groupId).orElseThrow(() -> ApiException.notFound("Grupo"));
        requireCommanderOrAdmin(me, g);
        if (me.id().equals(userId)) {
            throw ApiException.invalid("own-password", "Para mudares a tua palavra-passe usa o teu perfil");
        }
        repo.membershipOf(userId).filter(x -> x.groupId().equals(groupId)).orElseThrow(() -> ApiException.notFound("Militar"));
        return resets.issue(userId, me.id());
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
