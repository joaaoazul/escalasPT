package pt.turnos.identity.internal;

import java.io.IOException;
import java.time.Clock;
import java.util.Base64;
import java.util.List;
import java.util.Set;
import java.util.UUID;

import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.MethodParameter;
import org.springframework.core.convert.converter.Converter;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.argon2.Argon2PasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtEncoder;
import org.springframework.security.oauth2.server.resource.InvalidBearerTokenException;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.security.oauth2.server.resource.web.BearerTokenResolver;
import org.springframework.security.oauth2.server.resource.web.DefaultBearerTokenResolver;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.www.BasicAuthenticationFilter;
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.filter.OncePerRequestFilter;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import com.nimbusds.jose.jwk.source.ImmutableSecret;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import pt.turnos.identity.CurrentUser;

@Configuration(proxyBeanMethods = false)
@EnableConfigurationProperties(SecurityProperties.class)
class SecurityConfig implements WebMvcConfigurer {

    static final String CLIENT_HEADER = "X-Requested-With";
    static final String CLIENT_VALUE = "turnos";
    private static final Set<String> UNSAFE = Set.of("POST", "PUT", "PATCH", "DELETE");

    @Bean
    SecurityFilterChain api(HttpSecurity http, SecurityProperties props, Sessions sessions, Clock clock) throws Exception {
        http
            .csrf(c -> c.disable())
            .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(a -> a
                .requestMatchers(HttpMethod.POST, "/api/v1/auth/register", "/api/v1/auth/login", "/api/v1/auth/refresh").permitAll()
                .requestMatchers("/actuator/health/**", "/api/v3/api-docs/**").permitAll()
                .anyRequest().authenticated())
            .oauth2ResourceServer(o -> o
                .bearerTokenResolver(cookieOrHeader(props))
                .jwt(j -> j.jwtAuthenticationConverter(activeSessionOnly(sessions, clock))))
            .addFilterBefore(new ClientHeaderFilter(), BasicAuthenticationFilter.class);
        return http.build();
    }

    /**
     * Defesa CSRF em profundidade: além dos cookies SameSite=Strict, os métodos que alteram estado exigem
     * {@code X-Requested-With: turnos} (um formulário de outro site não o consegue enviar sem preflight CORS).
     * Clientes nativos que usam {@code Authorization: Bearer} não precisam dele.
     */
    static final class ClientHeaderFilter extends OncePerRequestFilter {
        @Override
        protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
                throws ServletException, IOException {
            boolean unsafe = UNSAFE.contains(req.getMethod());
            boolean bearer = req.getHeader(HttpHeaders.AUTHORIZATION) != null;
            if (unsafe && !bearer && !CLIENT_VALUE.equals(req.getHeader(CLIENT_HEADER))) {
                res.setStatus(HttpServletResponse.SC_FORBIDDEN);
                res.setContentType(MediaType.APPLICATION_PROBLEM_JSON_VALUE);
                res.getWriter().write("{\"type\":\"https://turnos.pt/problems/client-header\",\"title\":\"Forbidden\",\"status\":403,"
                        + "\"code\":\"client-header\",\"detail\":\"Pedido sem o cabeçalho X-Requested-With\"}");
                return;
            }
            chain.doFilter(req, res);
        }
    }

    private static BearerTokenResolver cookieOrHeader(SecurityProperties props) {
        DefaultBearerTokenResolver header = new DefaultBearerTokenResolver();
        return req -> {
            String fromHeader = header.resolve(req);
            if (fromHeader != null) {
                return fromHeader;
            }
            if (req.getCookies() != null) {
                for (var c : req.getCookies()) {
                    if (c.getName().equals(props.accessCookie()) && !c.getValue().isBlank()) {
                        return c.getValue();
                    }
                }
            }
            return null;
        };
    }

    /** O JWT só vale enquanto a sessão (dispositivo) não tiver sido revogada: logout é imediato. */
    private static Converter<Jwt, AbstractAuthenticationToken> activeSessionOnly(Sessions sessions, Clock clock) {
        return jwt -> {
            String sid = jwt.getClaimAsString("sid");
            if (sid == null || !sessions.isActive(UUID.fromString(sid), clock.instant())) {
                throw new InvalidBearerTokenException("Sessão revogada");
            }
            String role = jwt.getClaimAsString("role");
            return new JwtAuthenticationToken(jwt, List.of(new SimpleGrantedAuthority("ROLE_" + role)), jwt.getSubject());
        };
    }

    @Bean
    SecretKey jwtKey(SecurityProperties props) {
        byte[] key = Base64.getDecoder().decode(props.jwtSecret());
        if (key.length < 32) {
            throw new IllegalStateException("turnos.security.jwt-secret tem de ter pelo menos 32 bytes (base64)");
        }
        return new SecretKeySpec(key, "HmacSHA256");
    }

    @Bean
    JwtEncoder jwtEncoder(SecretKey key) {
        return new NimbusJwtEncoder(new ImmutableSecret<>(key));
    }

    @Bean
    JwtDecoder jwtDecoder(SecretKey key) {
        return NimbusJwtDecoder.withSecretKey(key).macAlgorithm(MacAlgorithm.HS256).build();
    }

    @Bean
    PasswordEncoder passwordEncoder() {
        return Argon2PasswordEncoder.defaultsForSpringSecurity_v5_8();
    }

    @Override
    public void addArgumentResolvers(List<HandlerMethodArgumentResolver> resolvers) {
        resolvers.add(new HandlerMethodArgumentResolver() {
            @Override
            public boolean supportsParameter(MethodParameter p) {
                return p.getParameterType() == CurrentUser.class;
            }

            @Override
            public Object resolveArgument(MethodParameter p, ModelAndViewContainer m, NativeWebRequest r, WebDataBinderFactory f) {
                Authentication a = SecurityContextHolder.getContext().getAuthentication();
                if (!(a instanceof JwtAuthenticationToken jwt)) {
                    throw new IllegalStateException("Sem utilizador autenticado");
                }
                boolean admin = a.getAuthorities().stream().anyMatch(g -> g.getAuthority().equals("ROLE_ADMIN"));
                return new CurrentUser(UUID.fromString(jwt.getToken().getSubject()), admin);
            }
        });
    }
}
