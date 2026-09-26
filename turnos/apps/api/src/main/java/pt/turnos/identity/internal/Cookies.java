package pt.turnos.identity.internal;

import java.time.Duration;

import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.stereotype.Component;

import jakarta.servlet.http.HttpServletResponse;

@Component
class Cookies {

    static final String REFRESH_PATH = "/api/v1/auth";

    private final SecurityProperties props;

    Cookies(SecurityProperties props) {
        this.props = props;
    }

    void write(HttpServletResponse res, String access, String refresh) {
        add(res, props.accessCookie(), access, "/", props.accessTokenTtl());
        add(res, props.refreshCookie(), refresh, REFRESH_PATH, props.refreshTokenTtl());
    }

    void clear(HttpServletResponse res) {
        add(res, props.accessCookie(), "", "/", Duration.ZERO);
        add(res, props.refreshCookie(), "", REFRESH_PATH, Duration.ZERO);
    }

    private void add(HttpServletResponse res, String name, String value, String path, Duration maxAge) {
        ResponseCookie c = ResponseCookie.from(name, value)
                .httpOnly(true).secure(props.cookieSecure()).sameSite("Strict").path(path).maxAge(maxAge).build();
        res.addHeader(HttpHeaders.SET_COOKIE, c.toString());
    }
}
