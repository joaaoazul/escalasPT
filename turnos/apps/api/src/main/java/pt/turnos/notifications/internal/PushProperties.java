package pt.turnos.notifications.internal;

import java.net.URI;
import java.util.List;
import java.util.Locale;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Chaves VAPID em base64url (pública: ponto P-256 não comprimido, 65 bytes; privada: 32 bytes).
 * Gerar com {@code npx web-push generate-vapid-keys}. Sem chaves, o Web Push fica desligado (as notificações in-app funcionam).
 */
@ConfigurationProperties("turnos.push")
record PushProperties(String vapidPublicKey, String vapidPrivateKey, String subject, List<String> allowedHosts) {

    boolean enabled() {
        return vapidPublicKey != null && !vapidPublicKey.isBlank() && vapidPrivateKey != null && !vapidPrivateKey.isBlank();
    }

    /**
     * O servidor faz POST para o endpoint da subscrição: só se aceitam os serviços de push conhecidos (evita SSRF).
     * HTTPS obrigatório, exceto para localhost quando está na lista (testes).
     */
    boolean allowedEndpoint(String endpoint) {
        try {
            URI uri = URI.create(endpoint);
            String host = uri.getHost() == null ? "" : uri.getHost().toLowerCase(Locale.ROOT);
            boolean local = host.equals("localhost") || host.equals("127.0.0.1");
            if (!"https".equals(uri.getScheme()) && !("http".equals(uri.getScheme()) && local)) {
                return false;
            }
            return allowedHosts != null && allowedHosts.stream().anyMatch(a -> host.equals(a) || host.endsWith("." + a));
        } catch (IllegalArgumentException e) {
            return false;
        }
    }
}
