package pt.turnos.importer.internal;

import java.time.LocalDate;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.core.env.Environment;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.stereotype.Component;

/**
 * Corre a importação e termina a aplicação. Exemplo:
 * <pre>
 * java -jar api.jar --turnos.import.escalaspt.url=jdbc:postgresql://host:5432/gnr_escalas \
 *   --turnos.import.escalaspt.user=… --turnos.import.escalaspt.password=… \
 *   --turnos.import.station-code=PT-CMR --turnos.import.group-name="Grupo 1" \
 *   --turnos.import.commander-email=… --turnos.import.from=2026-09-01
 * </pre>
 */
@Component
@ConditionalOnProperty("turnos.import.escalaspt.url")
class ImportRunner implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(ImportRunner.class);

    private final EscalasPtImporter importer;
    private final Environment env;
    private final ConfigurableApplicationContext context;

    ImportRunner(EscalasPtImporter importer, Environment env, ConfigurableApplicationContext context) {
        this.importer = importer;
        this.env = env;
        this.context = context;
    }

    @Override
    public void run(ApplicationArguments args) {
        DriverManagerDataSource source = new DriverManagerDataSource(env.getRequiredProperty("turnos.import.escalaspt.url"),
                env.getProperty("turnos.import.escalaspt.user", ""), env.getProperty("turnos.import.escalaspt.password", ""));
        EscalasPtImporter.Options opt = new EscalasPtImporter.Options(
                env.getRequiredProperty("turnos.import.station-code"),
                env.getProperty("turnos.import.group-name", "Grupo 1"),
                env.getProperty("turnos.import.commander-email"),
                LocalDate.parse(env.getProperty("turnos.import.from", LocalDate.now().minusDays(90).toString())));
        int code = 0;
        try {
            EscalasPtImporter.Report r = importer.run(source, opt);
            log.info("Importado '{}': {} tipos de serviço, {} militares novos, {} já existentes, {} serviços",
                    r.postoName(), r.types(), r.militaresCreated(), r.militaresReused(), r.shifts());
            r.skipped().forEach(s -> log.warn("Não importado: {}", s));
        } catch (RuntimeException e) {
            log.error("Importação falhou: {}", e.getMessage());
            code = 1;
        }
        int exit = code;
        System.exit(org.springframework.boot.SpringApplication.exit(context, () -> exit));
    }
}
