import requests
from functools import partial

from connector.common import BackendRequest
from connector.tools import request_with_broker_retry
from connector.processor import register_processor


class AGDREFConnector:

    def __init__(self):
        self.disabled = True
        self._backend_requests = None
        self._agdref_request = None
        self.processors = {}

    def init_app(self, app):
        app.config.setdefault('DISABLE_CONNECTOR_AGDREF', False)
        app.config.setdefault('DISABLE_CONNECTOR_AGDREF_INPUT', False)
        app.config.setdefault('CONNECTOR_AGDREF_USERNAME', '')
        app.config.setdefault('CONNECTOR_AGDREF_PASSWORD', '')
        app.config.setdefault('CONNECTOR_AGDREF_TOKEN', '')
        app.config.setdefault('CONNECTOR_AGDREF_URL', 'http://127.0.0.1')
        app.config.setdefault('CONNECTOR_AGDREF_EXPOSED_URL', '')
        app.config.setdefault('CONNECTOR_AGDREF_HTTP_PROXY', '')
        app.config.setdefault('CONNECTOR_AGDREF_HTTPS_PROXY', '')
        app.config.setdefault('CONNECTOR_AGDREF_PREFIX', '/connectors/agdref')
        app.config.setdefault('CONNECTOR_AGDREF_REQUESTS', requests)
        app.config.setdefault('CONNECTOR_AGDREF_TIMEOUT', 60)

        self.timeout = app.config['CONNECTOR_AGDREF_TIMEOUT']
        self.disabled = app.config['DISABLE_CONNECTOR_AGDREF']
        self.disabled_input = app.config['DISABLE_CONNECTOR_AGDREF_INPUT']
        self.requests = app.config['CONNECTOR_AGDREF_REQUESTS']
        self.connector_domain = (app.config['BACKEND_URL_DOMAIN'] +
                                 app.config['CONNECTOR_AGDREF_PREFIX'])
        self.exp_url = app.config['CONNECTOR_AGDREF_EXPOSED_URL']
        if self.exp_url in (None, ''):
            self.exp_url = self.connector_domain
        self.server = app.config['CONNECTOR_AGDREF_SERVER']
        self._backend_requests = BackendRequest(
            domain=app.config['BACKEND_URL_DOMAIN'],
            url_prefix=app.config['BACKEND_API_PREFIX'],
            auth=(app.config['CONNECTOR_AGDREF_USERNAME'], app.config['CONNECTOR_AGDREF_PASSWORD']),
            token=app.config['CONNECTOR_AGDREF_TOKEN'],
            requests=app.config['CONNECTOR_AGDREF_REQUESTS'])
        proxies = {
            'http': app.config['CONNECTOR_AGDREF_HTTP_PROXY'],
            'https': app.config['CONNECTOR_AGDREF_HTTPS_PROXY']
        }
        self._agdref_request = request_with_broker_retry(partial(
            app.config['CONNECTOR_AGDREF_REQUESTS'].request, method='POST',
            url=app.config['CONNECTOR_AGDREF_URL'], proxies=proxies,
            timeout=self.timeout))
        self.build_processors()
        if not app.config.get('CONNECTOR_AGDREF_PARTIAL'):
            self.connect_routes(app)
        self._fake_on_dna = app.config.get('FAKE_ON_DNA', False)  # TODO: remove me !

    def build_processors(self):
        from connector.agdref.decision_definitive_ofpra import DecisionDefinitiveOFPRACNDA
        from connector.agdref.demande_numero_ou_validation import DemandeNumeroOuValidationRequest
        from connector.agdref.edition_attestation_demande_asile import EditionAttestationDemandeAsile
        from connector.agdref.edition_attestation_demande_asile import EditionAttestationDemandeAsileRefus
        from connector.agdref.enregistrement_demandeur_inerec import EnregistrementDemandeurINEREC
        from connector.agdref.mise_a_jour_adresse_ofpra_ofii import MiseAJourAdresse
        from connector.agdref.reconstitution_etat_civil_OFPRA import ReconstitutionEtatCivilOFPRA
        from connector.agdref.requalification_procedure import RequalificationProcedure

        # Connect processors
        for key, connector_cls in (
                ('agdref_decision_definitive_ofpra', DecisionDefinitiveOFPRACNDA),
                ('agdref_demande_numero_ou_validation', DemandeNumeroOuValidationRequest),
                ('agdref_edition_attestation_demande_asile', EditionAttestationDemandeAsile),
                ('agdref_edition_attestation_demande_asile_refus',
                 EditionAttestationDemandeAsileRefus),
                ('agdref_enregistrement_demandeur_inerec', EnregistrementDemandeurINEREC),
                ('agdref_mise_a_jour_adresse', MiseAJourAdresse),
                ('agdref_reconstitution_etat_civil_OFPRA', ReconstitutionEtatCivilOFPRA),
                ('agdref_requalification_procedure', RequalificationProcedure),
        ):
            self.processors[key] = register_processor(connector_cls(self), name=key)

    def connect_routes(self, app):
        from connector.agdref.agdref_input import MajAGDREF
        from flask.ext.restful import Api
        connector_api = Api(app, prefix=app.config['CONNECTOR_AGDREF_PREFIX'])
        connector_api.add_resource(MajAGDREF, '/majAGDREF')

    @property
    def backend_requests(self):
        if self.disabled or not self._backend_requests:
            raise RuntimeError('Connecteur non initialisé')
        return self._backend_requests

    @property
    def agdref_request(self):
        if self.disabled or not self._agdref_request:
            raise RuntimeError('Connecteur non initialisé')
        return self._agdref_request


connector_agdref = AGDREFConnector()
init_connector_agdref = connector_agdref.init_app


__all__ = ('connector_agdref', 'init_connector_agdref')
