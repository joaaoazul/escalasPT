package pt.turnos.identity.internal;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import pt.turnos.identity.UserDirectory;
import pt.turnos.identity.UserSummary;

@Repository
class Users implements UserDirectory {

    private static final String COLUMNS = "id, email, password_hash, full_name, rank, service_number, system_role, failed_logins, locked_until";

    private final JdbcClient jdbc;

    Users(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    Optional<UserRow> byEmail(String email) {
        return jdbc.sql("SELECT " + COLUMNS + " FROM users WHERE email = :email")
                .param("email", email).query(Users::map).optional();
    }

    Optional<UserRow> byId(UUID id) {
        return jdbc.sql("SELECT " + COLUMNS + " FROM users WHERE id = :id").param("id", id).query(Users::map).optional();
    }

    boolean emailTaken(String email) {
        return jdbc.sql("SELECT count(*) FROM users WHERE email = :email").param("email", email).query(Long.class).single() > 0;
    }

    void insert(UUID id, String email, String hash, String fullName, String rank, String number, String role, Instant now) {
        jdbc.sql("""
                INSERT INTO users (id, email, password_hash, full_name, rank, service_number, system_role, created_at, updated_at)
                VALUES (:id, :email, :hash, :name, :rank, :number, :role, :now, :now)""")
                .param("id", id).param("email", email).param("hash", hash).param("name", fullName)
                .param("rank", rank).param("number", number).param("role", role).param("now", Timestamp.from(now))
                .update();
    }

    void recordFailedLogin(UUID id, int max, Instant lockUntil) {
        jdbc.sql("""
                UPDATE users SET failed_logins = failed_logins + 1,
                       locked_until = CASE WHEN failed_logins + 1 >= :max THEN :until ELSE locked_until END
                WHERE id = :id""")
                .param("id", id).param("max", max).param("until", Timestamp.from(lockUntil)).update();
    }

    void updatePassword(UUID id, String hash, Instant now) {
        jdbc.sql("UPDATE users SET password_hash = :h, updated_at = :now WHERE id = :id")
                .param("id", id).param("h", hash).param("now", Timestamp.from(now)).update();
    }

    void updateProfile(UUID id, String fullName, String rank, String number, Instant now) {
        jdbc.sql("UPDATE users SET full_name = :n, rank = :r, service_number = :s, updated_at = :now WHERE id = :id")
                .param("id", id).param("n", fullName).param("r", rank).param("s", number).param("now", Timestamp.from(now)).update();
    }

    void resetFailedLogins(UUID id) {
        jdbc.sql("UPDATE users SET failed_logins = 0, locked_until = NULL WHERE id = :id").param("id", id).update();
    }

    @Override
    public Optional<UserSummary> find(UUID id) {
        return byId(id).map(UserRow::summary);
    }

    @Override
    public List<UserSummary> findAll(Collection<UUID> ids) {
        if (ids.isEmpty()) {
            return List.of();
        }
        return jdbc.sql("SELECT " + COLUMNS + " FROM users WHERE id IN (:ids)").param("ids", ids)
                .query(Users::map).list().stream().map(UserRow::summary).toList();
    }

    private static UserRow map(ResultSet rs, int n) throws SQLException {
        Timestamp locked = rs.getTimestamp("locked_until");
        return new UserRow(rs.getObject("id", UUID.class), rs.getString("email"), rs.getString("password_hash"),
                rs.getString("full_name"), rs.getString("rank"), rs.getString("service_number"),
                rs.getString("system_role"), rs.getInt("failed_logins"), locked == null ? null : locked.toInstant());
    }
}
