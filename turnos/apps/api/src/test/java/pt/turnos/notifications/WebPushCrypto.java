package pt.turnos.notifications;

import java.nio.ByteBuffer;
import java.security.KeyPair;
import java.security.PrivateKey;
import java.security.interfaces.ECPublicKey;
import java.util.Arrays;

import javax.crypto.Cipher;
import javax.crypto.KeyAgreement;
import javax.crypto.Mac;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;

import java.nio.charset.StandardCharsets;

/** Lado do browser (user agent) do RFC 8291: decifra o que o servidor envia. Só para testes. */
public final class WebPushCrypto {

    private WebPushCrypto() {
    }

    public static byte[] decrypt(byte[] body, PrivateKey uaPrivate, byte[] uaPublic, byte[] authSecret) throws Exception {
        ByteBuffer bb = ByteBuffer.wrap(body);
        byte[] salt = new byte[16];
        bb.get(salt);
        bb.getInt(); // record size
        byte[] asPublic = new byte[bb.get() & 0xff];
        bb.get(asPublic);
        byte[] ciphertext = new byte[bb.remaining()];
        bb.get(ciphertext);

        KeyAgreement ka = KeyAgreement.getInstance("ECDH");
        ka.init(uaPrivate);
        ka.doPhase(toPublic(asPublic), true);
        byte[] ecdh = ka.generateSecret();

        byte[] keyInfo = concat("WebPush: info".getBytes(StandardCharsets.US_ASCII), new byte[] {0}, uaPublic, asPublic);
        byte[] ikm = hkdf(authSecret, ecdh, keyInfo, 32);
        byte[] cek = hkdf(salt, ikm, concat("Content-Encoding: aes128gcm".getBytes(StandardCharsets.US_ASCII), new byte[] {0}), 16);
        byte[] nonce = hkdf(salt, ikm, concat("Content-Encoding: nonce".getBytes(StandardCharsets.US_ASCII), new byte[] {0}), 12);
        Cipher gcm = Cipher.getInstance("AES/GCM/NoPadding");
        gcm.init(Cipher.DECRYPT_MODE, new SecretKeySpec(cek, "AES"), new GCMParameterSpec(128, nonce));
        byte[] padded = gcm.doFinal(ciphertext);
        int end = padded.length - 1;
        while (end >= 0 && padded[end] == 0) {
            end--;
        }
        if (padded[end] != 0x02) {
            throw new IllegalStateException("Delimitador de último registo em falta");
        }
        return Arrays.copyOf(padded, end);
    }

    static ECPublicKey toPublic(byte[] uncompressed) throws Exception {
        java.math.BigInteger x = new java.math.BigInteger(1, Arrays.copyOfRange(uncompressed, 1, 33));
        java.math.BigInteger y = new java.math.BigInteger(1, Arrays.copyOfRange(uncompressed, 33, 65));
        java.security.AlgorithmParameters p = java.security.AlgorithmParameters.getInstance("EC");
        p.init(new java.security.spec.ECGenParameterSpec("secp256r1"));
        return (ECPublicKey) java.security.KeyFactory.getInstance("EC").generatePublic(
                new java.security.spec.ECPublicKeySpec(new java.security.spec.ECPoint(x, y), p.getParameterSpec(java.security.spec.ECParameterSpec.class)));
    }

    public static byte[] encodePublic(KeyPair kp) {
        ECPublicKey k = (ECPublicKey) kp.getPublic();
        byte[] out = new byte[65];
        out[0] = 4;
        System.arraycopy(fixed(k.getW().getAffineX().toByteArray()), 0, out, 1, 32);
        System.arraycopy(fixed(k.getW().getAffineY().toByteArray()), 0, out, 33, 32);
        return out;
    }

    private static byte[] fixed(byte[] b) {
        if (b.length == 32) {
            return b;
        }
        byte[] out = new byte[32];
        System.arraycopy(b, Math.max(0, b.length - 32), out, Math.max(0, 32 - b.length), Math.min(32, b.length));
        return out;
    }

    private static byte[] hkdf(byte[] salt, byte[] ikm, byte[] info, int len) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(salt, "HmacSHA256"));
        byte[] prk = mac.doFinal(ikm);
        mac.init(new SecretKeySpec(prk, "HmacSHA256"));
        mac.update(info);
        mac.update((byte) 1);
        return Arrays.copyOf(mac.doFinal(), len);
    }

    private static byte[] concat(byte[]... parts) {
        int n = 0;
        for (byte[] p : parts) {
            n += p.length;
        }
        ByteBuffer b = ByteBuffer.allocate(n);
        for (byte[] p : parts) {
            b.put(p);
        }
        return b.array();
    }
}
