package pt.turnos.units.internal;

import java.util.UUID;

import org.springframework.stereotype.Component;

import pt.turnos.identity.RegistrationInvites;

/** Liga o registo de conta (identity) aos convites de grupo de folgas. */
@Component
class InviteRegistration implements RegistrationInvites {

    private final UnitsService service;

    InviteRegistration(UnitsService service) {
        this.service = service;
    }

    @Override
    public void check(String code, String email) {
        service.checkForRegistration(code, email);
    }

    @Override
    public void redeem(String code, UUID userId) {
        service.acceptFor(userId, code);
    }
}
