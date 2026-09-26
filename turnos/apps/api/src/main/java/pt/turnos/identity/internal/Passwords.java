package pt.turnos.identity.internal;

import org.springframework.security.crypto.argon2.Argon2PasswordEncoder;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;

/**
 * Palavras-passe novas em Argon2id. As importadas do EscalasPT chegam em bcrypt (passlib, "$2b$") com o prefixo
 * {@code {bcrypt}}: continuam a funcionar e são convertidas para Argon2id no primeiro login ({@link #upgradeEncoding}).
 */
final class Passwords implements PasswordEncoder {

    static final String LEGACY_BCRYPT = "{bcrypt}";

    private final Argon2PasswordEncoder argon2 = Argon2PasswordEncoder.defaultsForSpringSecurity_v5_8();
    private final BCryptPasswordEncoder bcrypt = new BCryptPasswordEncoder();

    @Override
    public String encode(CharSequence raw) {
        return argon2.encode(raw);
    }

    @Override
    public boolean matches(CharSequence raw, String encoded) {
        if (encoded == null) {
            return false;
        }
        if (encoded.startsWith(LEGACY_BCRYPT)) {
            return bcrypt.matches(raw, encoded.substring(LEGACY_BCRYPT.length()));
        }
        return argon2.matches(raw, encoded);
    }

    @Override
    public boolean upgradeEncoding(String encoded) {
        return encoded != null && encoded.startsWith(LEGACY_BCRYPT);
    }
}
