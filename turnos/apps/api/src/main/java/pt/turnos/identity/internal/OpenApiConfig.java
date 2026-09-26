package pt.turnos.identity.internal;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.Set;
import java.util.TreeSet;

import org.springdoc.core.customizers.OpenApiCustomizer;
import org.springdoc.core.utils.SpringDocUtils;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.media.Schema;
import pt.turnos.identity.CurrentUser;

/**
 * Ajustes ao contrato gerado (fonte do cliente TypeScript):
 * <ul>
 *   <li>{@link CurrentUser} vem da sessão, não é um parâmetro do pedido;</li>
 *   <li>nas respostas todos os campos estão sempre presentes (podem é valer null): marcam-se como required.
 *       Nos pedidos ficam só os obrigatórios de facto (@NotNull, @NotBlank…).</li>
 * </ul>
 */
@Configuration(proxyBeanMethods = false)
class OpenApiConfig {

    static {
        SpringDocUtils.getConfig().addRequestWrapperToIgnore(CurrentUser.class);
    }

    @Bean
    OpenApiCustomizer responsesHaveAllFields() {
        return api -> {
            if (api.getComponents() == null || api.getComponents().getSchemas() == null) {
                return;
            }
            Set<String> responseSchemas = new HashSet<>();
            api.getPaths().values().forEach(item -> item.readOperations().forEach(op -> {
                if (op.getResponses() != null) {
                    op.getResponses().values().forEach(r -> {
                        if (r.getContent() != null) {
                            r.getContent().values().forEach(mt -> collect(api, mt.getSchema(), responseSchemas));
                        }
                    });
                }
            }));
            for (String name : responseSchemas) {
                Schema<?> s = api.getComponents().getSchemas().get(name);
                if (s != null && s.getProperties() != null) {
                    s.setRequired(new ArrayList<>(new TreeSet<>(s.getProperties().keySet())));
                }
            }
        };
    }

    private static void collect(OpenAPI api, Schema<?> schema, Set<String> out) {
        if (schema == null) {
            return;
        }
        if (schema.get$ref() != null) {
            String name = schema.get$ref().substring(schema.get$ref().lastIndexOf('/') + 1);
            if (out.add(name)) {
                collect(api, api.getComponents().getSchemas().get(name), out);
            }
            return;
        }
        collect(api, schema.getItems(), out);
        if (schema.getProperties() != null) {
            schema.getProperties().values().forEach(p -> collect(api, p, out));
        }
        if (schema.getAdditionalProperties() instanceof Schema<?> ap) {
            collect(api, ap, out);
        }
    }
}
