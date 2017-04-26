import requests
from requests.exceptions import RequestException
import xmltodict
from datetime import datetime
from functools import namedtuple
from connector.agdref.demande_numero_ou_validation import DemandeNumeroOuValidationRequest
from connector.tools import strip_namespaces
from connector.debugger import RequestDebugger


AGDREFNumberResult = namedtuple(
    'AGDREFNumberResult', ('identifiant_agdref', 'identifiant_portail_agdref',
                           'date_enregistrement_agdref'))


class AGDREFNumberError(Exception):
    pass


class AGDREFDisabled(Exception):
    pass


class AGDREFConnectionError(Exception):
    pass


class AGDREFRequiredFieldsError(Exception):

    def __init__(self, errors):
        super().__init__()
        self.errors = errors


class NumAGDREFRequest:

    def __init__(self):
        self.disabled = False
        self.build_soap_request = DemandeNumeroOuValidationRequest(
            connector=None).build_soap_request

    def init_app(self, app):
        app.config.setdefault('DISABLE_AGDREF_NUM', False)
        app.config.setdefault('AGDREF_NUM_TESTING_STUB', False)
        app.config.setdefault('AGDREF_NUM_REQUESTS', requests)
        app.config.setdefault('AGDREF_NUM_URL', 'http://127.0.0.1')
        self.requests = app.config['AGDREF_NUM_REQUESTS']
        self.requests = RequestDebugger(self.requests)
        self._fake_on_dna = app.config.get('FAKE_ON_DNA', False)  # TODO: remove me !
        self.testing_stub = app.config.get('AGDREF_NUM_TESTING_STUB')
        self.disabled = app.config.get('DISABLE_AGDREF_NUM')
        self.url = app.config.get('AGDREF_NUM_URL')
        if not self.testing_stub and not self.url:
            self.disabled = True

    def _check_and_extract_required(self, usager):
        missing = []
        extracted = {}
        for attr in ("nom", "prenoms", "sexe", "date_naissance",
                     "pays_naissance", "ville_naissance", "situation_familiale",
                     "nationalites", "date_entree_en_france", "identifiant_portail_agdref",
                     "origine_nom", "photo"):
            value = getattr(usager, attr, None)
            if value in ('', None):
                missing.append(attr)
            else:
                extracted[attr] = value
        if getattr(usager, 'nom_usage', None):
            if getattr(usager, 'origine_nom_usage', None) in ('', None):
                missing.append('origine_nom_usage')

        def serial_ref(ref):
            if ref and hasattr(ref, 'code'):
                return {'code': ref.code}
        extracted['pays_naissance'] = serial_ref(extracted.get('pays_naissance'))
        extracted['nationalites'] = [serial_ref(nat) for nat in extracted.get('nationalites', ())]
        if missing:
            errors = {}
            for elt in missing:
                errors[elt] = "Champ requis"
            raise AGDREFRequiredFieldsError(errors)
        return extracted

    def _build_xml(self, usager, code_departement):
        return self.build_soap_request(usager, {}, code_departement=code_departement, numero_da=0)

    def _parse(self, msg):
        raw = xmltodict.parse(msg)
        # Remove soap_enveloppe
        raw = raw.popitem()[1]
        raw = raw.popitem()[1]
        raw = raw.popitem()[1]
        raw = strip_namespaces(raw)

        if raw.get('codeErreur') != '000':
            # Change exception to Process Message Exception
            raise AGDREFNumberError(
                "Le serveur distant AGDREF a renvoyé une erreur %s" % raw.get('codeErreur'))
        return AGDREFNumberResult(
            identifiant_agdref=raw.get('numeroRessortissantEtranger'),
            identifiant_portail_agdref=raw.get('identifiantSIAsile'),
            date_enregistrement_agdref=datetime.strptime(
                '%s-%s' % (raw['dateEnregistrementAGDREF'], raw['heureEnregistrementAGDREF']),
                "%Y%m%d-%H%M%S")
        )

    def _submit_query(self, xml):
        if xml is None:
            raise AGDREFNumberError('No data to send through connector')
        try:
            req = self.requests.post(self.url, data=xml)
        except RequestException:
            raise AGDREFConnectionError('Erreur lors de la connexion avec AGDREF')
        if req.ok:
            return self._parse(req.text)
        else:
            raise AGDREFNumberError('La reponse renvoyee par AGDREF n\'a pu etre analysee')

    def query(self, usager, code_departement):
        if self.disabled:
            raise AGDREFDisabled('Connecteur AGDREF Désactivé')
        # TODO: remove me !!!
        if self.testing_stub or (self._fake_on_dna and usager.nom.endswith(' dna')):
            from random import choice
            from string import digits, ascii_letters
            return AGDREFNumberResult(
                identifiant_agdref=''.join(choice(digits) for _ in range(10)),
                identifiant_portail_agdref=''.join(
                    choice(digits + ascii_letters) for _ in range(12)),
                date_enregistrement_agdref=datetime.utcnow()
            )
        self._check_and_extract_required(usager)
        return self._submit_query(self._build_xml(usager, code_departement))


agdref_requestor = NumAGDREFRequest()
enregistrement_agdref = agdref_requestor.query
