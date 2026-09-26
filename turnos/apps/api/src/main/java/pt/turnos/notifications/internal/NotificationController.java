package pt.turnos.notifications.internal;

import java.time.Clock;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import pt.turnos.identity.CurrentUser;
import pt.turnos.shared.ApiException;
import pt.turnos.shared.Ids;

@RestController
@RequestMapping("/api/v1")
@EnableConfigurationProperties(PushProperties.class)
class NotificationController {

    record NotificationDto(UUID id, String type, String title, String body, String url, Instant readAt, Instant createdAt) {
    }

    record Inbox(long unread, List<NotificationDto> items) {
    }

    record Keys(@NotBlank @Size(max = 200) String p256dh, @NotBlank @Size(max = 100) String auth) {
    }

    record Subscribe(@NotBlank @Size(max = 1000) String endpoint, @NotNull @Valid Keys keys) {
    }

    record Unsubscribe(@NotBlank String endpoint) {
    }

    record PushConfig(boolean enabled, String publicKey) {
    }

    private final NotificationRepository repo;
    private final PushSender push;
    private final PushProperties props;
    private final Clock clock;

    NotificationController(NotificationRepository repo, PushSender push, PushProperties props, Clock clock) {
        this.repo = repo;
        this.props = props;
        this.push = push;
        this.clock = clock;
    }

    @GetMapping("/notifications")
    Inbox inbox(CurrentUser me) {
        return new Inbox(repo.unread(me.id()), repo.latest(me.id(), 50).stream()
                .map(n -> new NotificationDto(n.id(), n.type(), n.title(), n.body(), n.url(), n.readAt(), n.createdAt())).toList());
    }

    @PostMapping("/notifications/read")
    Map<String, Integer> readAll(CurrentUser me) {
        return Map.of("updated", repo.markAllRead(me.id(), clock.instant()));
    }

    @GetMapping("/push/config")
    PushConfig config() {
        return new PushConfig(push.enabled(), push.enabled() ? push.publicKey() : null);
    }

    @PostMapping("/push/subscriptions")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    void subscribe(CurrentUser me, @Valid @RequestBody Subscribe req) {
        if (!push.enabled()) {
            throw ApiException.invalid("push-disabled", "As notificações no telemóvel não estão ativas neste servidor");
        }
        if (!props.allowedEndpoint(req.endpoint())) {
            throw ApiException.invalid("push-endpoint-not-allowed", "Serviço de notificações não reconhecido");
        }
        repo.upsertSubscription(Ids.newId(), me.id(), req.endpoint(), req.keys().p256dh(), req.keys().auth(), clock.instant());
    }

    @DeleteMapping("/push/subscriptions")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    void unsubscribe(CurrentUser me, @Valid @RequestBody Unsubscribe req) {
        repo.deleteSubscription(me.id(), req.endpoint());
    }
}
