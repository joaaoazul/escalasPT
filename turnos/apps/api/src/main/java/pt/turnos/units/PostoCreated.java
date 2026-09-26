package pt.turnos.units;

import java.util.UUID;

/** Publicado na criação de um posto (o módulo scheduling cria os tipos de serviço por omissão). */
public record PostoCreated(UUID postoId) {
}
