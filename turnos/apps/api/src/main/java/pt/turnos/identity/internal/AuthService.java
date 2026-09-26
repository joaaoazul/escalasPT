package pt.turnos.identity.internal;

import java.time.Clock;
import java.time.Instant;
import java.util.Locale;
import java.util.UUID;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.annotation.Propagation;

import pt.turnos.shared.ApiException;
import pt.turnos.shared.Ids;

@Service
class AuthService {

    record Issued(UserRow user, String accessToken, String refreshToken) {
    }

    private static final ApiException BAD_CREDENTIALS =
            new ApiException(HttpStatus.UNAUTHORIZED, "bad-credentials", "Email ou palavra-passe incorretos");

    private final Users users;
    private final Sessions sessions;
    private final Tokens tokens;
    private final PasswordEncoder passwords;
    private final SecurityProperties props;
    private final Clock clock;
    private final String bootstrapAdmin;
    /** Hash descartável para gastar o mesmo tempo quando o email não existe (evita enumeração por tempo). */
    private final String dummyHash;

    AuthService(Users users, Sessions sessions, Tokens tokens, PasswordEncoder passwords, SecurityProperties props,
                Clock clock, @Value("${turnos.bootstrap-admin-email:}") String bootstrapAdmin) {
        this.users = users;
        this.sessions = sessions;
        this.tokens = tokens;
        this.passwords = passwords;
        this.props = props;
        this.clock = clock;
        this.bootstrapAdmin = bootstrapAdmin == null ? "" : bootstrapAdmin.trim().toLowerCase(Locale.ROOT);
        this.dummyHash = passwords.encode("turnos-dummy-password");
    }

    @Transactional
    Issued register(AuthController.RegisterRequest req, String userAgent) {
        String email = req.email().trim().toLowerCase(Locale.ROOT);
        if (users.emailTaken(email)) {
            throw ApiException.conflict("email-taken", "Já existe uma conta com este email");
        }
        UUID id = Ids.newId();
        String role = !bootstrapAdmin.isEmpty() && bootstrapAdmin.equals(email) ? "ADMIN" : "USER";
        users.insert(id, email, passwords.encode(req.password()), req.fullName().trim(), blankToNull(req.rank()),
                blankToNull(req.serviceNumber()), role, clock.instant());
        return openSession(users.byId(id).orElseThrow(), userAgent);
    }

    /** As falhas de login ficam gravadas mesmo quando o pedido termina em 401 (noRollbackFor). */
    @Transactional(noRollbackFor = ApiException.class)
    Issued login(String rawEmail, String password, String userAgent) {
        Instant now = clock.instant();
        UserRow user = users.byEmail(rawEmail.trim().toLowerCase(Locale.ROOT)).orElse(null);
        if (user == null) {
            passwords.matches(password, dummyHash);
            throw BAD_CREDENTIALS;
        }
        if (user.lockedUntil() != null && user.lockedUntil().isAfter(now)) {
            throw new ApiException(HttpStatus.LOCKED, "account-locked", "Conta bloqueada temporariamente por tentativas falhadas");
        }
        if (!passwords.matches(password, user.passwordHash())) {
            users.recordFailedLogin(user.id(), props.maxFailedLogins(), now.plus(props.lockout()));
            throw BAD_CREDENTIALS;
        }
        if (user.failedLogins() > 0) {
            users.resetFailedLogins(user.id());
        }
        if (passwords.upgradeEncoding(user.passwordHash())) {
            users.updatePassword(user.id(), passwords.encode(password), now);
        }
        return openSession(user, userAgent);
    }

    @Transactional(noRollbackFor = ApiException.class)
    Issued refresh(String refreshToken) {
        Instant now = clock.instant();
        if (refreshToken == null || refreshToken.isBlank()) {
            throw unauthorized();
        }
        byte[] hash = Tokens.hash(refreshToken);
        Sessions.Session s = sessions.byCurrentHashForUpdate(hash).orElse(null);
        if (s == null) {
            // Token antigo reutilizado: alguém o copiou. Revoga a sessão inteira.
            sessions.byPreviousHash(hash).ifPresent(old -> sessions.revoke(old.id(), now));
            throw unauthorized();
        }
        if (s.revokedAt() != null || !s.expiresAt().isAfter(now)) {
            throw unauthorized();
        }
        String next = Tokens.newRefreshToken();
        sessions.rotate(s.id(), hash, Tokens.hash(next), now);
        UserRow user = users.byId(s.userId()).orElseThrow(this::unauthorized);
        return new Issued(user, tokens.accessToken(user, s.id(), now), next);
    }

    @Transactional
    void logout(UUID sessionId) {
        sessions.revoke(sessionId, clock.instant());
    }

    @Transactional
    UserRow updateProfile(UUID id, String fullName, String rank, String number) {
        UserRow u = users.byId(id).orElseThrow(this::unauthorized);
        users.updateProfile(id, fullName == null || fullName.isBlank() ? u.fullName() : fullName.trim(),
                rank == null ? u.rank() : blankToNull(rank), number == null ? u.serviceNumber() : blankToNull(number), clock.instant());
        return users.byId(id).orElseThrow();
    }

    @Transactional(readOnly = true, propagation = Propagation.SUPPORTS)
    UserRow me(UUID id) {
        return users.byId(id).orElseThrow(this::unauthorized);
    }

    private Issued openSession(UserRow user, String userAgent) {
        Instant now = clock.instant();
        UUID sid = Ids.newId();
        String refresh = Tokens.newRefreshToken();
        sessions.create(sid, user.id(), Tokens.hash(refresh), userAgent, now, now.plus(props.refreshTokenTtl()));
        return new Issued(user, tokens.accessToken(user, sid, now), refresh);
    }

    private ApiException unauthorized() {
        return new ApiException(HttpStatus.UNAUTHORIZED, "auth-required", "Sessão inválida ou expirada");
    }

    private static String blankToNull(String s) {
        return s == null || s.isBlank() ? null : s.trim();
    }
}
