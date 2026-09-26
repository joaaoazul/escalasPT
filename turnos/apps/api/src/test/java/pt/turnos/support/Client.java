package pt.turnos.support;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.request;

import java.util.LinkedHashMap;
import java.util.Map;

import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

import jakarta.servlet.http.Cookie;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/** Um "browser" de teste: guarda os cookies entre pedidos e envia o cabeçalho X-Requested-With. */
public class Client {

    public record Res(int status, JsonNode body, MockHttpServletResponse raw) {
        public String text(String field) {
            return body.path(field).asString();
        }
    }

    private final MockMvc mvc;
    private final JsonMapper json;
    private final Map<String, Cookie> jar = new LinkedHashMap<>();
    private boolean clientHeader = true;

    public Client(MockMvc mvc, JsonMapper json) {
        this.mvc = mvc;
        this.json = json;
    }

    public Client withoutClientHeader() {
        clientHeader = false;
        return this;
    }

    public Map<String, Cookie> cookies() {
        return jar;
    }

    public Res get(String path) {
        return send(HttpMethod.GET, path, null);
    }

    public Res post(String path, Object body) {
        return send(HttpMethod.POST, path, body);
    }

    public Res put(String path, Object body) {
        return send(HttpMethod.PUT, path, body);
    }

    public Res patch(String path, Object body) {
        return send(HttpMethod.PATCH, path, body);
    }

    public Res delete(String path) {
        return send(HttpMethod.DELETE, path, null);
    }

    public Res send(HttpMethod method, String path, Object body) {
        try {
            MockHttpServletRequestBuilder b = request(method, path);
            if (clientHeader) {
                b.header("X-Requested-With", "turnos");
            }
            if (body != null) {
                b.contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(body));
            }
            if (!jar.isEmpty()) {
                b.cookie(jar.values().toArray(Cookie[]::new));
            }
            MockHttpServletResponse r = mvc.perform(b).andReturn().getResponse();
            for (String header : r.getHeaders(HttpHeaders.SET_COOKIE)) {
                String[] kv = header.split(";", 2)[0].split("=", 2);
                if (kv[1].isEmpty()) {
                    jar.remove(kv[0]);
                } else {
                    jar.put(kv[0], new Cookie(kv[0], kv[1]));
                }
            }
            byte[] bytes = r.getContentAsByteArray();
            String type = r.getContentType();
            JsonNode node = bytes.length > 0 && type != null && type.contains("json") ? json.readTree(bytes) : json.nullNode();
            return new Res(r.getStatus(), node, r);
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }
}
