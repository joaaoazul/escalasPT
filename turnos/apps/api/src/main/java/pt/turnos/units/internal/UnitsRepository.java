package pt.turnos.units.internal;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.time.ZoneId;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import pt.turnos.units.Membership;
import pt.turnos.units.PostoInfo;
import pt.turnos.units.Units;

@Repository
class UnitsRepository implements Units {

    record Group(UUID id, UUID postoId, String name) {
    }

    record Invite(UUID id, UUID groupId, String email, String inviteeName, String inviteeRank, String role,
                  Instant expiresAt, UUID createdBy, Instant createdAt, UUID acceptedBy, Instant acceptedAt, Instant revokedAt) {
    }

    private static final String MEMBERSHIP = """
            SELECT m.user_id, g.posto_id, g.id AS group_id, g.name AS group_name, m.role
            FROM group_members m JOIN folga_groups g ON g.id = m.group_id""";

    private final JdbcClient jdbc;

    UnitsRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    // ── postos e grupos ──

    void insertPosto(UUID id, String name, String location, String zone, Instant now) {
        jdbc.sql("INSERT INTO postos (id, name, location, time_zone, created_at) VALUES (:id, :n, :l, :z, :now)")
                .param("id", id).param("n", name).param("l", location).param("z", zone).param("now", Timestamp.from(now)).update();
    }

    void insertGroup(UUID id, UUID postoId, String name, Instant now) {
        jdbc.sql("INSERT INTO folga_groups (id, posto_id, name, created_at) VALUES (:id, :p, :n, :now)")
                .param("id", id).param("p", postoId).param("n", name).param("now", Timestamp.from(now)).update();
    }

    Optional<Group> group(UUID id) {
        return jdbc.sql("SELECT id, posto_id, name FROM folga_groups WHERE id = :id").param("id", id)
                .query((rs, n) -> new Group(rs.getObject("id", UUID.class), rs.getObject("posto_id", UUID.class), rs.getString("name")))
                .optional();
    }

    List<Group> groupsOfPosto(UUID postoId) {
        return jdbc.sql("SELECT id, posto_id, name FROM folga_groups WHERE posto_id = :p ORDER BY name").param("p", postoId)
                .query((rs, n) -> new Group(rs.getObject("id", UUID.class), rs.getObject("posto_id", UUID.class), rs.getString("name")))
                .list();
    }

    @Override
    public Optional<PostoInfo> posto(UUID id) {
        return jdbc.sql("SELECT id, name, location, time_zone FROM postos WHERE id = :id").param("id", id)
                .query((rs, n) -> new PostoInfo(rs.getObject("id", UUID.class), rs.getString("name"), rs.getString("location"),
                        ZoneId.of(rs.getString("time_zone"))))
                .optional();
    }

    // ── membros ──

    @Override
    public Optional<Membership> membershipOf(UUID userId) {
        return jdbc.sql(MEMBERSHIP + " WHERE m.user_id = :u").param("u", userId).query(UnitsRepository::membership).optional();
    }

    @Override
    public List<Membership> membersOfPosto(UUID postoId) {
        return jdbc.sql(MEMBERSHIP + " WHERE g.posto_id = :p ORDER BY g.name, m.joined_at").param("p", postoId)
                .query(UnitsRepository::membership).list();
    }

    void addMember(UUID groupId, UUID userId, String role, Instant now) {
        jdbc.sql("INSERT INTO group_members (group_id, user_id, role, joined_at) VALUES (:g, :u, :r, :now)")
                .param("g", groupId).param("u", userId).param("r", role).param("now", Timestamp.from(now)).update();
    }

    int removeMember(UUID groupId, UUID userId) {
        return jdbc.sql("DELETE FROM group_members WHERE group_id = :g AND user_id = :u").param("g", groupId).param("u", userId).update();
    }

    Optional<UUID> membershipOfGroupCommander(UUID groupId) {
        return jdbc.sql("SELECT user_id FROM group_members WHERE group_id = :g AND role = 'COMMANDER'").param("g", groupId)
                .query(UUID.class).optional();
    }

    void setRole(UUID groupId, UUID userId, String role) {
        jdbc.sql("UPDATE group_members SET role = :r WHERE group_id = :g AND user_id = :u")
                .param("g", groupId).param("u", userId).param("r", role).update();
    }

    // ── convites ──

    void insertInvite(UUID id, UUID groupId, byte[] tokenHash, String email, String name, String rank, String role,
                      Instant expiresAt, UUID createdBy, Instant now) {
        jdbc.sql("""
                INSERT INTO group_invites (id, group_id, token_hash, email, invitee_name, invitee_rank, role, expires_at, created_by, created_at)
                VALUES (:id, :g, :h, :e, :n, :r, :role, :exp, :by, :now)""")
                .param("id", id).param("g", groupId).param("h", tokenHash).param("e", email).param("n", name).param("r", rank)
                .param("role", role).param("exp", Timestamp.from(expiresAt)).param("by", createdBy).param("now", Timestamp.from(now))
                .update();
    }

    List<Invite> invitesOfGroup(UUID groupId) {
        return jdbc.sql("SELECT * FROM group_invites WHERE group_id = :g ORDER BY created_at DESC").param("g", groupId)
                .query(UnitsRepository::invite).list();
    }

    Optional<Invite> inviteByHash(byte[] hash) {
        return jdbc.sql("SELECT * FROM group_invites WHERE token_hash = :h").param("h", hash).query(UnitsRepository::invite).optional();
    }

    /** Consome o convite de forma atómica: só um pedido o consegue usar. */
    boolean consumeInvite(UUID id, UUID userId, Instant now) {
        return jdbc.sql("""
                UPDATE group_invites SET accepted_by = :u, accepted_at = :now
                WHERE id = :id AND accepted_at IS NULL AND revoked_at IS NULL AND expires_at > :now""")
                .param("id", id).param("u", userId).param("now", Timestamp.from(now)).update() == 1;
    }

    boolean revokeInvite(UUID id, UUID groupId, Instant now) {
        return jdbc.sql("UPDATE group_invites SET revoked_at = :now WHERE id = :id AND group_id = :g AND accepted_at IS NULL AND revoked_at IS NULL")
                .param("id", id).param("g", groupId).param("now", Timestamp.from(now)).update() == 1;
    }

    private static Membership membership(ResultSet rs, int n) throws SQLException {
        return new Membership(rs.getObject("user_id", UUID.class), rs.getObject("posto_id", UUID.class),
                rs.getObject("group_id", UUID.class), rs.getString("group_name"), "COMMANDER".equals(rs.getString("role")));
    }

    private static Invite invite(ResultSet rs, int n) throws SQLException {
        return new Invite(rs.getObject("id", UUID.class), rs.getObject("group_id", UUID.class), rs.getString("email"),
                rs.getString("invitee_name"), rs.getString("invitee_rank"), rs.getString("role"), instant(rs, "expires_at"),
                rs.getObject("created_by", UUID.class), instant(rs, "created_at"), rs.getObject("accepted_by", UUID.class),
                instant(rs, "accepted_at"), instant(rs, "revoked_at"));
    }

    private static Instant instant(ResultSet rs, String col) throws SQLException {
        Timestamp t = rs.getTimestamp(col);
        return t == null ? null : t.toInstant();
    }
}
