package pt.turnos.identity.internal;

import java.util.UUID;

import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import pt.turnos.identity.CurrentUser;

@RestController
@RequestMapping("/api/v1")
class AuthController {

    record RegisterRequest(
            @NotBlank @Email @Size(max = 200) String email,
            @NotBlank @Size(min = 10, max = 200) String password,
            @NotBlank @Size(max = 120) String fullName,
            @Size(max = 40) String rank,
            @Pattern(regexp = "^[0-9]{1,5}$") String serviceNumber) {
    }

    record LoginRequest(@NotBlank String email, @NotBlank String password) {
    }

    /** Campos ausentes ficam como estão; string vazia apaga (posto e n.º de ordem). */
    record ProfileRequest(@Size(min = 1, max = 120) String fullName, @Size(max = 40) String rank,
                          @Pattern(regexp = "^([0-9]{1,5})?$") String serviceNumber) {
    }

    record MeResponse(UUID id, String email, String fullName, String rank, String serviceNumber, boolean admin) {
        static MeResponse of(UserRow u) {
            return new MeResponse(u.id(), u.email(), u.fullName(), u.rank(), u.serviceNumber(), u.admin());
        }
    }

    private final AuthService auth;
    private final Cookies cookies;
    private final SecurityProperties props;

    AuthController(AuthService auth, Cookies cookies, SecurityProperties props) {
        this.auth = auth;
        this.cookies = cookies;
        this.props = props;
    }

    @PostMapping("/auth/register")
    @ResponseStatus(HttpStatus.CREATED)
    MeResponse register(@Valid @RequestBody RegisterRequest req,
                        @RequestHeader(value = HttpHeaders.USER_AGENT, required = false) String ua,
                        HttpServletResponse res) {
        AuthService.Issued issued = auth.register(req, ua);
        cookies.write(res, issued.accessToken(), issued.refreshToken());
        return MeResponse.of(issued.user());
    }

    @PostMapping("/auth/login")
    MeResponse login(@Valid @RequestBody LoginRequest req,
                     @RequestHeader(value = HttpHeaders.USER_AGENT, required = false) String ua,
                     HttpServletResponse res) {
        AuthService.Issued issued = auth.login(req.email(), req.password(), ua);
        cookies.write(res, issued.accessToken(), issued.refreshToken());
        return MeResponse.of(issued.user());
    }

    @PostMapping("/auth/refresh")
    MeResponse refresh(HttpServletRequest req, HttpServletResponse res) {
        AuthService.Issued issued = auth.refresh(cookie(req, props.refreshCookie()));
        cookies.write(res, issued.accessToken(), issued.refreshToken());
        return MeResponse.of(issued.user());
    }

    @PostMapping("/auth/logout")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    void logout(@AuthenticationPrincipal Jwt jwt, HttpServletResponse res) {
        auth.logout(UUID.fromString(jwt.getClaimAsString("sid")));
        cookies.clear(res);
    }

    @GetMapping("/me")
    MeResponse me(CurrentUser user) {
        return MeResponse.of(auth.me(user.id()));
    }

    @PatchMapping("/me")
    MeResponse updateProfile(CurrentUser user, @Valid @RequestBody ProfileRequest req) {
        return MeResponse.of(auth.updateProfile(user.id(), req.fullName(), req.rank(), req.serviceNumber()));
    }

    private static String cookie(HttpServletRequest req, String name) {
        if (req.getCookies() == null) {
            return null;
        }
        for (var c : req.getCookies()) {
            if (c.getName().equals(name)) {
                return c.getValue();
            }
        }
        return null;
    }
}
