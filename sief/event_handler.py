from connector.processor import processor_manager
from sief.model.utilisateur import Utilisateur
from sief.tasks.email import mail


class ValidationError(Exception):
    pass


def canceled_message_and_send_mail(message, exception, origin=None):
    subject = "Message %s CANCELLED par le système" % str(message.id)
    body = """Bonjour,
Le message (id :%s) de la file %s a été automatiquement passé en CANCELLED par le système.

Exception: %s

Cordialement,
-- Mailer Daemon""" % (str(message.id), str(origin), str(exception))
    administrateurs_national = Utilisateur.objects(accreditations__role='ADMINISTRATEUR_NATIONAL')
    for administrateur_national in administrateurs_national:
        mail.send(subject=subject, recipient=administrateur_national.email, body=body)
    return 'CANCELLED'


def _check_processor(value):
    if not processor_manager.find(value):
        raise ValidationError('Unknown processor %s' % value)
    return True


EVENT_HANDLERS_TEMPLATE = [
    {
        "label": "inerec-demande_asile.procedure_requalifiee",
        "origin": "inerec",
        "queue": "inerec",
        "processor": "webhook",
        "event": "demande_asile.procedure_requalifiee",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "inerec-demande_asile.en_attente_ofpra",
        "origin": "inerec",
        "queue": "inerec",
        "processor": "webhook",
        "event": "demande_asile.en_attente_ofpra",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "inerec-demande_asile.decision_attestation",
        "origin": "inerec",
        "queue": "inerec",
        "processor": "webhook",
        "event": "demande_asile.decision_attestation",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "inerec-usager.etat_civil.modifie",
        "origin": "inerec",
        "queue": "inerec",
        "processor": "webhook",
        "event": "usager.etat_civil.modifie",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "inerec-usager.modifie",
        "origin": "inerec",
        "queue": "inerec",
        "processor": "webhook",
        "event": "usager.modifie",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "inerec-usager.localisation.modifie",
        "origin": "inerec",
        "queue": "inerec",
        "processor": "webhook",
        "event": "usager.localisation.modifie",
        "on_error_callback": canceled_message_and_send_mail,
        "to_rabbit": True
    },
    {
        "label": "dna-recueil_da.pa_realise",
        "origin": "dna",
        "queue": "dna",
        "processor": "dna_recuperer_donnees_portail",
        "event": "recueil_da.pa_realise",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "dna-recueil_da.exploite",
        "origin": "dna",
        "queue": "dna",
        "processor": "dna_recuperer_donnees_portail",
        "event": "recueil_da.exploite",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "dna-recueil_da.exploite_by_step",
        "origin": "dna",
        "queue": "dna",
        "processor": "dna_recuperer_donnees_portail_by_step",
        "event": "recueil_da.exploite_by_step",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "dna-demande_asile.procedure_requalifiee",
        "origin": "dna",
        "queue": "dna",
        "processor": "dna_majda",
        "event": "demande_asile.procedure_requalifiee",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "dna-demande_asile.procedure_finie",
        "origin": "dna",
        "queue": "dna",
        "processor": "dna_majda",
        "event": "demande_asile.procedure_finie",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "dna-demande_asile.dublin_modifie",
        "origin": "dna",
        "queue": "dna",
        "processor": "dna_majda",
        "event": "demande_asile.dublin_modifie",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "dna-demande_asile.decision_definitive",
        "origin": "dna",
        "queue": "dna",
        "processor": "dna_majda",
        "event": "demande_asile.decision_definitive",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "dna-usager.etat_civil.valide",
        "origin": "dna",
        "queue": "dna",
        "processor": "dna_majda",
        "event": "usager.etat_civil.valide",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "inerec-droit.cree",
        "origin": "inerec",
        "queue": "inerec",
        "processor": "webhook",
        "event": "droit.cree",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "inerec-droit.retire",
        "origin": "inerec",
        "queue": "inerec",
        "processor": "webhook",
        "event": "droit.retire",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "inerec-droit.modifie",
        "origin": "inerec",
        "queue": "inerec",
        "processor": "webhook",
        "event": "droit.modifie",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "inerec-droit.support.cree",
        "origin": "inerec",
        "queue": "inerec",
        "processor": "webhook",
        "event": "droit.support.cree",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "inerec-droit.support.modifie",
        "origin": "inerec",
        "queue": "inerec",
        "processor": "webhook",
        "event": "droit.support.modifie",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "agdref-demande_asile.decision_definitive",
        "origin": "agdref",
        "queue": "agdref",
        "processor": "agdref_decision_definitive_ofpra",
        "event": "demande_asile.decision_definitive",
        "on_error_callback": canceled_message_and_send_mail,
        "to_skip": True
    },
    {
        "label": "dna-demande_asile.introduit_ofpra",
        "origin": "dna",
        "queue": "dna",
        "processor": "dna_majda",
        "event": "demande_asile.introduit_ofpra",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "inerec-droit.support.annule",
        "origin": "inerec",
        "queue": "inerec",
        "processor": "webhook",
        "event": "droit.support.annule",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "inerec-demande_asile.modifie",
        "origin": "inerec",
        "queue": "inerec",
        "processor": "webhook",
        "event": "demande_asile.modifie",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "agdref-droit.support.cree",
        "origin": "agdref",
        "queue": "agdref",
        "processor": "agdref_edition_attestation_demande_asile",
        "event": "droit.support.cree",
        "on_error_callback": canceled_message_and_send_mail
    },
    # This processor contains new information for AGDREF (stream 05)
    # It is temporary disabled and will be reactivated later.
    # {
    #     "label": "agdref-droit.refus",
    #     "origin": "agdref",
    #     "queue": "agdref",
    #     "processor": "agdref_edition_attestation_demande_asile_refus",
    #     "event": "droit.refus",
    #     "on_error_callback": canceled_message_and_send_mail
    # },
    {
        "label": "agdref-demande_asile.procedure_requalifiee",
        "origin": "agdref",
        "queue": "agdref",
        "processor": "agdref_requalification_procedure",
        "event": "demande_asile.procedure_requalifiee",
        "to_skip": True,
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "agdref-usager.etat_civil.valide",
        "origin": "agdref",
        "queue": "agdref",
        "processor": "agdref_reconstitution_etat_civil_OFPRA",
        "to_skip": True,
        "event": "usager.etat_civil.valide",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "agdref-demande_asile.introduit_ofpra",
        "origin": "agdref",
        "queue": "agdref",
        "processor": "agdref_enregistrement_demandeur_inerec",
        "event": "demande_asile.introduit_ofpra",
        "to_skip": True,
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "agdref-demande_asile.cree",
        "origin": "agdref",
        "queue": "agdref",
        "processor": "agdref_demande_numero_ou_validation",
        "event": "demande_asile.cree",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "agdref-usager.etat_civil.modifie",
        "origin": "agdref",
        "queue": "agdref",
        "processor": "agdref_demande_numero_ou_validation",
        "event": "usager.etat_civil.modifie",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "dna-usager.etat_civil.modifie",
        "origin": "dna",
        "queue": "dna",
        "processor": "dna_majda",
        "event": "usager.etat_civil.modifie",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "dna-usager.modifie",
        "origin": "dna",
        "queue": "dna",
        "processor": "dna_majda",
        "event": "usager.modifie",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "dna-demande_asile.attestation_edite",
        "origin": "dna",
        "queue": "dna",
        "processor": "dna_majda",
        "event": "demande_asile.attestation_edite",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "dna-droit.cree",
        "origin": "dna",
        "queue": "dna",
        "processor": "dna_majda",
        "event": "droit.cree",
        "on_error_callback": canceled_message_and_send_mail
    },
    {
        "label": "analytics-recueil_da.modifie",
        "origin": "analytics",
        "queue": "analytics",
        "processor": "analytics_pa_realise_on_error",
        "event": "recueil_da.modifie",
    },
    {
        "label": "analytics-usager.prefecture_rattachee.modifie",
        "origin": "analytics",
        "queue": "analytics",
        "processor": "analytics_transfert_prefecture",
        "event": "usager.prefecture_rattachee.modifie",
    },
]

MAIL_ALERT_HANDLER_TEMPLATE = {
    "label": "alerte-demande_asile.decision_definitive",
    "queue": "mailing",
    "processor": "mail_demande_asile_rejected",
    "event": "demande_asile.decision_definitive"
}


def event_handlers_factory(app):
    event_handlers = EVENT_HANDLERS_TEMPLATE.copy()
    inerec_id = dna_id = agdref_id = None
    email = app.config['CONNECTOR_DNA_USERNAME']
    dna = Utilisateur.objects(email=email).first()
    if not dna:
        app.logger.warning('System user dna (%s) is not present' % email)
    else:
        dna_id = dna.id
    email = app.config['CONNECTOR_AGDREF_USERNAME']
    agdref = Utilisateur.objects(email=email).first()
    if not agdref:
        app.logger.warning('System user agdref (%s) is not present' % email)
    else:
        agdref_id = agdref.id
    email = app.config['CONNECTOR_INEREC_USERNAME']
    inerec = Utilisateur.objects(email=email).first()
    if not inerec:
        app.logger.warning('System user inerec (%s) is not present' % email)
    else:
        inerec_id = inerec.id
    inerec_proxies = {
        'http': app.config.get('CONNECTOR_INEREC_HTTP_PROXY'),
        'https': app.config.get('CONNECTOR_INEREC_HTTPS_PROXY'),
    }
    for item in event_handlers:
        if not app.config.get('CONNECTOR_AGDREF_PARTIAL'):
            if item.get('to_skip'):
                del item['to_skip']
        if item.get('origin') == 'dna':
            item['origin'] = dna_id
        if item.get('origin') == 'agdref':
            item['origin'] = agdref_id
        if item.get('origin') == 'inerec':
            item['origin'] = inerec_id
            item['context'] = {'proxies': inerec_proxies,
                               'url': app.config.get('CONNECTOR_INEREC_URL', '')}

    if app.config['FF_ENABLE_MAIL_ALERT']:
        event_handlers.append(MAIL_ALERT_HANDLER_TEMPLATE.copy())

    return event_handlers
