package pt.turnos.swaps.internal;

import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/** Expira, a cada minuto, os pedidos cujo prazo (fim da véspera do serviço) já passou. */
@Component
public class SwapExpiryJob {

    private final SwapService swaps;

    SwapExpiryJob(SwapService swaps) {
        this.swaps = swaps;
    }

    @Scheduled(fixedDelayString = "${turnos.swaps.expiry-interval:PT1M}")
    public int run() {
        return swaps.expire();
    }
}
