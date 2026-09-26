package pt.turnos.shared;

import java.util.List;
import java.util.Map;

import org.springframework.http.HttpStatus;

/**
 * Erro de negócio traduzido para RFC 9457 pelo {@link ProblemHandler}.
 * O {@code code} é estável (o cliente traduz por ele); a mensagem é em pt-PT.
 */
public class ApiException extends RuntimeException {

    private final HttpStatus status;
    private final String code;
    private final List<Map<String, Object>> violations;

    public ApiException(HttpStatus status, String code, String message) {
        this(status, code, message, List.of());
    }

    public ApiException(HttpStatus status, String code, String message, List<Map<String, Object>> violations) {
        super(message);
        this.status = status;
        this.code = code;
        this.violations = violations;
    }

    public HttpStatus status() {
        return status;
    }

    public String code() {
        return code;
    }

    public List<Map<String, Object>> violations() {
        return violations;
    }

    public static ApiException notFound(String what) {
        return new ApiException(HttpStatus.NOT_FOUND, "not-found", what + " não encontrado");
    }

    public static ApiException forbidden(String message) {
        return new ApiException(HttpStatus.FORBIDDEN, "forbidden", message);
    }

    public static ApiException invalid(String code, String message) {
        return new ApiException(HttpStatus.UNPROCESSABLE_CONTENT, code, message);
    }

    public static ApiException conflict(String code, String message) {
        return new ApiException(HttpStatus.CONFLICT, code, message);
    }
}
