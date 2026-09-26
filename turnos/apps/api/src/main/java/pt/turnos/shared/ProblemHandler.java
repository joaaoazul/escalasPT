package pt.turnos.shared;

import java.net.URI;
import java.util.List;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/** Traduz erros para Problem Details (RFC 9457) com {@code code} estável. */
@RestControllerAdvice
public class ProblemHandler {

    private static final Logger log = LoggerFactory.getLogger(ProblemHandler.class);

    @ExceptionHandler(ApiException.class)
    ResponseEntity<ProblemDetail> api(ApiException e) {
        return build(e.status(), e.code(), e.getMessage(), e.violations());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    ResponseEntity<ProblemDetail> validation(MethodArgumentNotValidException e) {
        List<Map<String, Object>> fields = e.getBindingResult().getFieldErrors().stream()
                .map(f -> Map.<String, Object>of("field", f.getField(), "message", String.valueOf(f.getDefaultMessage())))
                .toList();
        return build(HttpStatus.BAD_REQUEST, "validation", "Dados inválidos", fields);
    }

    /** Última linha de defesa: as constraints da BD (sobreposição, unicidade) chegam aqui se uma corrida escapar à validação. */
    @ExceptionHandler(DataIntegrityViolationException.class)
    ResponseEntity<ProblemDetail> integrity(DataIntegrityViolationException e) {
        String msg = String.valueOf(e.getMostSpecificCause().getMessage());
        log.info("Violação de integridade: {}", msg);
        if (msg.contains("shifts_no_overlap") || msg.contains("shifts_one_all_day")) {
            return build(HttpStatus.UNPROCESSABLE_CONTENT, "shift-conflict", "O serviço sobrepõe-se a outro serviço do militar", List.of());
        }
        if (msg.contains("swap_one_active")) {
            return build(HttpStatus.CONFLICT, "swap-already-active", "Esse serviço já tem um pedido de troca ativo", List.of());
        }
        return build(HttpStatus.CONFLICT, "conflict", "O pedido entra em conflito com dados existentes", List.of());
    }

    private static ResponseEntity<ProblemDetail> build(HttpStatus status, String code, String detail, List<Map<String, Object>> violations) {
        ProblemDetail pd = ProblemDetail.forStatusAndDetail(status, detail);
        pd.setType(URI.create("https://turnos.pt/problems/" + code));
        pd.setTitle(status.getReasonPhrase());
        pd.setProperty("code", code);
        if (!violations.isEmpty()) {
            pd.setProperty("violations", violations);
        }
        return ResponseEntity.status(status).body(pd);
    }
}
