package pt.turnos.notifications.internal;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.security.KeyPair;
import java.security.Signature;
import java.time.Instant;
import java.util.Base64;

import org.junit.jupiter.api.Test;

import pt.turnos.notifications.WebPushCrypto;

class WebPushTest {

    private static final Base64.Decoder D = Base64.getUrlDecoder();
    private static final Base64.Encoder E = Base64.getUrlEncoder().withoutPadding();

    /** Exemplo do RFC 8291, secção 5: com as mesmas chaves e salt, o resultado tem de ser byte a byte o mesmo. */
    @Test
    void vetorDeTesteDoRfc8291() throws Exception {
        byte[] asPublic = D.decode("BP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A8");
        byte[] asPrivate = D.decode("yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw");
        byte[] uaPublic = D.decode("BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4");
        byte[] auth = D.decode("BTBZMqHH6r4Tts7J_aSIgg");
        byte[] salt = D.decode("DGv6ra1nlYgDCS1FRnbzlw");
        KeyPair as = new KeyPair(WebPush.decodePublic(asPublic), WebPush.decodePrivate(asPrivate));

        byte[] body = WebPush.encrypt("When I grow up, I want to be a watermelon".getBytes(StandardCharsets.UTF_8), uaPublic, auth, as, salt);

        assertThat(E.encodeToString(body)).isEqualTo(
                "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_"
                        + "yl95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN");
    }

    @Test
    void oBrowserDecifraOQueOServidorCifra() throws Exception {
        KeyPair ua = WebPush.newKeyPair();
        byte[] uaPublic = WebPush.encode((java.security.interfaces.ECPublicKey) ua.getPublic());
        byte[] auth = WebPush.randomBytes(16);
        String msg = "{\"title\":\"Pedido de troca\",\"body\":\"Cabo Rui Rocha quer trocar o teu AT2 de 07/10 pelo OC3.\"}";

        byte[] body = WebPush.encrypt(msg.getBytes(StandardCharsets.UTF_8), E.encodeToString(uaPublic), E.encodeToString(auth));

        assertThat(new String(WebPushCrypto.decrypt(body, ua.getPrivate(), uaPublic, auth), StandardCharsets.UTF_8)).isEqualTo(msg);
    }

    @Test
    void cabecalhoVapidTemJwtEs256Valido() throws Exception {
        KeyPair vapid = WebPush.newKeyPair();
        byte[] pub = WebPush.encode((java.security.interfaces.ECPublicKey) vapid.getPublic());
        String h = WebPush.vapidAuthorization("https://fcm.googleapis.com/fcm/send/abc", "mailto:a@b.pt", pub,
                (java.security.interfaces.ECPrivateKey) vapid.getPrivate(), Instant.parse("2026-09-26T10:00:00Z"));

        assertThat(h).startsWith("vapid t=").contains(", k=" + E.encodeToString(pub));
        String jwt = h.substring(8, h.indexOf(','));
        String[] parts = jwt.split("\\.");
        assertThat(new String(D.decode(parts[1]), StandardCharsets.UTF_8))
                .contains("\"aud\":\"https://fcm.googleapis.com\"").contains("\"sub\":\"mailto:a@b.pt\"");
        Signature v = Signature.getInstance("SHA256withECDSAinP1363Format");
        v.initVerify(vapid.getPublic());
        v.update((parts[0] + "." + parts[1]).getBytes(StandardCharsets.US_ASCII));
        assertThat(v.verify(D.decode(parts[2]))).isTrue();
    }

    @Test
    void soServicosDePushConhecidos() {
        PushProperties p = new PushProperties("x", "y", null, java.util.List.of("fcm.googleapis.com", "push.apple.com"));
        assertThat(p.allowedEndpoint("https://fcm.googleapis.com/fcm/send/abc")).isTrue();
        assertThat(p.allowedEndpoint("https://web.push.apple.com/abc")).isTrue();
        assertThat(p.allowedEndpoint("http://fcm.googleapis.com/abc")).isFalse();
        assertThat(p.allowedEndpoint("https://evilfcm.googleapis.com.example/abc")).isFalse();
        assertThat(p.allowedEndpoint("https://169.254.169.254/latest")).isFalse();
        assertThat(p.allowedEndpoint("http://localhost:8080/api")).isFalse();
    }
}
