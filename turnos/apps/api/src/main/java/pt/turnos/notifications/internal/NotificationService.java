package pt.turnos.notifications.internal;

import java.time.Clock;
import java.time.Duration;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.UUID;

import org.springframework.context.ApplicationEventPublisher;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Async;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

import pt.turnos.identity.UserDirectory;
import pt.turnos.identity.UserSummary;
import pt.turnos.shared.Ids;
import pt.turnos.swaps.SwapEvent;

/**
 * Transforma os eventos das trocas em notificações. A notificação in-app é gravada na mesma transação da troca
 * (nunca se perde); o Web Push é enviado depois do commit, fora do pedido.
 */
@Service
class NotificationService {

    record Outgoing(UUID userId, String type, String title, String body, String url) {
    }

    /** Evento interno: há notificações novas para enviar por push depois do commit. */
    record PushBatch(List<Outgoing> items) {
    }

    private static final DateTimeFormatter DAY = DateTimeFormatter.ofPattern("dd/MM");
    private static final String URL = "/grupo?s=trocas";

    private final NotificationRepository repo;
    private final PushSender push;
    private final UserDirectory users;
    private final Clock clock;
    private final ApplicationEventPublisher events;

    NotificationService(NotificationRepository repo, PushSender push, UserDirectory users, Clock clock,
                        ApplicationEventPublisher events) {
        this.repo = repo;
        this.push = push;
        this.users = users;
        this.clock = clock;
        this.events = events;
    }

    @EventListener
    void on(SwapEvent e) {
        String requester = name(e.requesterId());
        String target = name(e.targetId());
        String day = e.date() == null ? "" : " de " + DAY.format(e.date());
        List<Outgoing> out = switch (e.type()) {
            case REQUESTED -> List.of(new Outgoing(e.targetId(), "SWAP_REQUESTED", "Pedido de troca",
                    requester + " quer trocar o teu " + e.targetShiftCode() + day + " pelo " + e.requesterShiftCode() + "."
                            + (e.note() == null ? "" : " “" + e.note() + "”"), URL));
            case HELD -> List.of(new Outgoing(e.requesterId(), "SWAP_HELD", target + " pediu para aguardar",
                    e.note() == null ? "Vai responder mais tarde ao pedido" + day + "." : "“" + e.note() + "”", URL));
            case ACCEPTED -> List.of(new Outgoing(e.requesterId(), "SWAP_ACCEPTED", "Troca aceite",
                    target + " aceitou a troca" + day + ". O documento de troca já está disponível.", URL));
            case DECLINED -> List.of(new Outgoing(e.requesterId(), "SWAP_DECLINED", "Troca recusada",
                    target + " recusou a troca" + day + (e.note() == null ? "." : ": “" + e.note() + "”"), URL));
            case CANCELLED -> List.of(new Outgoing(e.targetId(), "SWAP_CANCELLED", "Pedido cancelado",
                    requester + " cancelou o pedido de troca" + day + ".", URL));
            case EXPIRED -> List.of(
                    new Outgoing(e.requesterId(), "SWAP_EXPIRED", "Pedido expirado", "O pedido de troca" + day + " expirou sem resposta.", URL),
                    new Outgoing(e.targetId(), "SWAP_EXPIRED", "Pedido expirado", "O pedido de troca" + day + " expirou sem resposta.", URL));
        };
        out.forEach(o -> repo.insert(Ids.newId(), o.userId(), o.type(), o.title(), o.body(), o.url(), clock.instant()));
        events.publishEvent(new PushBatch(out));
    }

    @Async
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT, fallbackExecution = true)
    void deliver(PushBatch batch) {
        batch.items().forEach(o -> push.send(o.userId(), o.title(), o.body(), o.url()));
    }

    /** Guarda 90 dias de notificações. */
    @Scheduled(cron = "0 17 3 * * *")
    void cleanup() {
        repo.deleteOlderThan(clock.instant().minus(Duration.ofDays(90)));
    }

    private String name(UUID id) {
        return users.find(id).map(UserSummary::displayName).orElse("Um camarada");
    }
}
