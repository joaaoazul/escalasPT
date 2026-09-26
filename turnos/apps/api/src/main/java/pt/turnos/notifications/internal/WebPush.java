package pt.turnos.notifications.internal;

import java.math.BigInteger;
import java.net.URI;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.AlgorithmParameters;
import java.security.GeneralSecurityException;
import java.security.KeyFactory;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.SecureRandom;
import java.security.Signature;
import java.security.interfaces.ECPrivateKey;
import java.security.interfaces.ECPublicKey;
import java.security.spec.ECGenParameterSpec;
import java.security.spec.ECParameterSpec;
import java.security.spec.ECPoint;
import java.security.spec.ECPrivateKeySpec;
import java.security.spec.ECPublicKeySpec;
import java.time.Instant;
import java.util.Arrays;
import java.util.Base64;

import javax.crypto.Cipher;
import javax.crypto.KeyAgreement;
import javax.crypto.Mac;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;

/**
 * Web Push sem dependências externas: cifra do conteúdo (RFC 8291, aes128gcm / RFC 8188) e autenticação VAPID
 * (RFC 8292, JWT ES256). Só usa a criptografia do JDK.
 */
final class WebPush {

    static final int RECORD_SIZE = 4096;
    private static final SecureRandom RANDOM = new SecureRandom();
    private static final Base64.Decoder B64 = Base64.getUrlDecoder();
    private static final Base64.Encoder B64E = Base64.getUrlEncoder().withoutPadding();

    private WebPush() {
    }

    // ── chaves P-256 ──

    static ECParameterSpec p256() {
        try {
            AlgorithmParameters params = AlgorithmParameters.getInstance("EC");
            params.init(new ECGenParameterSpec("secp256r1"));
            return params.getParameterSpec(ECParameterSpec.class);
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException(e);
        }
    }

    static KeyPair newKeyPair() {
        try {
            KeyPairGenerator g = KeyPairGenerator.getInstance("EC");
            g.initialize(new ECGenParameterSpec("secp256r1"));
            return g.generateKeyPair();
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException(e);
        }
    }

    /** Ponto não comprimido: 0x04 || X (32) || Y (32). */
    static byte[] encode(ECPublicKey key) {
        byte[] out = new byte[65];
        out[0] = 0x04;
        System.arraycopy(fixed32(key.getW().getAffineX()), 0, out, 1, 32);
        System.arraycopy(fixed32(key.getW().getAffineY()), 0, out, 33, 32);
        return out;
    }

    static ECPublicKey decodePublic(byte[] uncompressed) throws GeneralSecurityException {
        if (uncompressed.length != 65 || uncompressed[0] != 0x04) {
            throw new GeneralSecurityException("Chave pública P-256 inválida");
        }
        ECPoint w = new ECPoint(new BigInteger(1, Arrays.copyOfRange(uncompressed, 1, 33)),
                new BigInteger(1, Arrays.copyOfRange(uncompressed, 33, 65)));
        return (ECPublicKey) KeyFactory.getInstance("EC").generatePublic(new ECPublicKeySpec(w, p256()));
    }

    static ECPrivateKey decodePrivate(byte[] d) throws GeneralSecurityException {
        return (ECPrivateKey) KeyFactory.getInstance("EC").generatePrivate(new ECPrivateKeySpec(new BigInteger(1, d), p256()));
    }

    static byte[] fixed32(BigInteger v) {
        byte[] b = v.toByteArray();
        if (b.length == 32) {
            return b;
        }
        byte[] out = new byte[32];
        System.arraycopy(b, Math.max(0, b.length - 32), out, Math.max(0, 32 - b.length), Math.min(32, b.length));
        return out;
    }

    // ── cifra do conteúdo (RFC 8291) ──

    /** Cifra {@code plaintext} para a subscrição (p256dh, auth) e devolve o corpo aes128gcm pronto a enviar. */
    static byte[] encrypt(byte[] plaintext, String p256dhB64, String authB64) throws GeneralSecurityException {
        return encrypt(plaintext, B64.decode(p256dhB64), B64.decode(authB64), newKeyPair(), randomBytes(16));
    }

    static byte[] encrypt(byte[] plaintext, byte[] uaPublic, byte[] authSecret, KeyPair asKeys, byte[] salt) throws GeneralSecurityException {
        if (plaintext.length + 1 + 16 > RECORD_SIZE) {
            throw new GeneralSecurityException("Conteúdo demasiado grande para um registo");
        }
        byte[] asPublic = encode((ECPublicKey) asKeys.getPublic());
        KeyAgreement ka = KeyAgreement.getInstance("ECDH");
        ka.init(asKeys.getPrivate());
        ka.doPhase(decodePublic(uaPublic), true);
        byte[] ecdhSecret = ka.generateSecret();

        byte[] keyInfo = concat("WebPush: info".getBytes(StandardCharsets.US_ASCII), new byte[] {0}, uaPublic, asPublic);
        byte[] ikm = hkdf(authSecret, ecdhSecret, keyInfo, 32);
        byte[] cek = hkdf(salt, ikm, concat("Content-Encoding: aes128gcm".getBytes(StandardCharsets.US_ASCII), new byte[] {0}), 16);
        byte[] nonce = hkdf(salt, ikm, concat("Content-Encoding: nonce".getBytes(StandardCharsets.US_ASCII), new byte[] {0}), 12);

        Cipher gcm = Cipher.getInstance("AES/GCM/NoPadding");
        gcm.init(Cipher.ENCRYPT_MODE, new SecretKeySpec(cek, "AES"), new GCMParameterSpec(128, nonce));
        byte[] ciphertext = gcm.doFinal(concat(plaintext, new byte[] {0x02})); // 0x02 = último registo

        ByteBuffer header = ByteBuffer.allocate(16 + 4 + 1 + asPublic.length);
        header.put(salt).putInt(RECORD_SIZE).put((byte) asPublic.length).put(asPublic);
        return concat(header.array(), ciphertext);
    }

    /** HKDF-SHA256 (extract + um bloco de expand chega para ≤ 32 bytes). */
    static byte[] hkdf(byte[] salt, byte[] ikm, byte[] info, int length) throws GeneralSecurityException {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(salt, "HmacSHA256"));
        byte[] prk = mac.doFinal(ikm);
        mac.init(new SecretKeySpec(prk, "HmacSHA256"));
        mac.update(info);
        mac.update((byte) 1);
        return Arrays.copyOf(mac.doFinal(), length);
    }

    // ── VAPID (RFC 8292) ──

    /** Cabeçalho Authorization: {@code vapid t=<jwt>, k=<chave pública>}. */
    static String vapidAuthorization(String endpoint, String subject, byte[] vapidPublic, ECPrivateKey vapidPrivate, Instant now)
            throws GeneralSecurityException {
        URI uri = URI.create(endpoint);
        String audience = uri.getScheme() + "://" + uri.getHost() + (uri.getPort() == -1 ? "" : ":" + uri.getPort());
        String header = B64E.encodeToString("{\"typ\":\"JWT\",\"alg\":\"ES256\"}".getBytes(StandardCharsets.UTF_8));
        String claims = B64E.encodeToString(("{\"aud\":\"" + audience + "\",\"exp\":" + now.plusSeconds(12 * 3600).getEpochSecond()
                + ",\"sub\":\"" + subject + "\"}").getBytes(StandardCharsets.UTF_8));
        Signature es256 = Signature.getInstance("SHA256withECDSAinP1363Format");
        es256.initSign(vapidPrivate);
        es256.update((header + "." + claims).getBytes(StandardCharsets.US_ASCII));
        String jwt = header + "." + claims + "." + B64E.encodeToString(es256.sign());
        return "vapid t=" + jwt + ", k=" + B64E.encodeToString(vapidPublic);
    }

    static byte[] randomBytes(int n) {
        byte[] b = new byte[n];
        RANDOM.nextBytes(b);
        return b;
    }

    static byte[] concat(byte[]... parts) {
        int len = 0;
        for (byte[] p : parts) {
            len += p.length;
        }
        ByteBuffer bb = ByteBuffer.allocate(len);
        for (byte[] p : parts) {
            bb.put(p);
        }
        return bb.array();
    }
}
