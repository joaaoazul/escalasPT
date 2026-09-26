package pt.turnos.notifications.internal;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.interfaces.ECPrivateKey;
import java.time.Clock;
import java.time.Duration;
import java.util.Base64;
import java.util.Map;
import java.util.UUID;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import tools.jackson.databind.json.JsonMapper;

/** Envia notificações Web Push para todos os dispositivos de um militar. */
@Component
class PushSender {

    private static final Logger log = LoggerFactory.getLogger(PushSender.class);

    private final NotificationRepository repo;
    private final PushProperties props;
    private final JsonMapper json;
    private final Clock clock;
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
    private final byte[] vapidPublic;
    private final ECPrivateKey vapidPrivate;

    PushSender(NotificationRepository repo, PushProperties props, JsonMapper json, Clock clock) throws GeneralSecurityException {
        this.repo = repo;
        this.props = props;
        this.json = json;
        this.clock = clock;
        if (props.enabled()) {
            this.vapidPublic = Base64.getUrlDecoder().decode(props.vapidPublicKey());
            this.vapidPrivate = WebPush.decodePrivate(Base64.getUrlDecoder().decode(props.vapidPrivateKey()));
            WebPush.decodePublic(vapidPublic); // falha cedo se a chave estiver mal copiada
        } else {
            this.vapidPublic = null;
            this.vapidPrivate = null;
            log.info("Web Push desligado (turnos.push.vapid-* não configurado)");
        }
    }

    boolean enabled() {
        return props.enabled();
    }

    String publicKey() {
        return props.vapidPublicKey();
    }

    void send(UUID userId, String title, String body, String url) {
        if (!props.enabled()) {
            return;
        }
        byte[] payload = json.writeValueAsString(Map.of("title", title, "body", body, "url", url == null ? "/" : url))
                .getBytes(StandardCharsets.UTF_8);
        for (NotificationRepository.Subscription s : repo.subscriptionsOf(userId)) {
            try {
                HttpRequest req = HttpRequest.newBuilder(URI.create(s.endpoint()))
                        .timeout(Duration.ofSeconds(10))
                        .header("Content-Encoding", "aes128gcm")
                        .header("Content-Type", "application/octet-stream")
                        .header("TTL", "86400")
                        .header("Urgency", "high")
                        .header("Authorization", WebPush.vapidAuthorization(s.endpoint(), subject(), vapidPublic, vapidPrivate, clock.instant()))
                        .POST(HttpRequest.BodyPublishers.ofByteArray(WebPush.encrypt(payload, s.p256dh(), s.auth())))
                        .build();
                int status = http.send(req, HttpResponse.BodyHandlers.discarding()).statusCode();
                if (status >= 200 && status < 300) {
                    repo.pushOk(s.id(), clock.instant());
                } else {
                    log.info("Push recusado ({}) para {}", status, s.id());
                    repo.pushFailed(s.id(), status == 404 || status == 410);
                }
            } catch (Exception e) {
                if (e instanceof InterruptedException) {
                    Thread.currentThread().interrupt();
                }
                log.info("Falha a enviar push para {}: {}", s.id(), e.toString());
                repo.pushFailed(s.id(), false);
            }
        }
    }

    private String subject() {
        return props.subject() == null || props.subject().isBlank() ? "mailto:suporte@turnos.pt" : props.subject();
    }
}
