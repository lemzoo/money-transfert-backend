from datetime import datetime
from unittest.mock import patch

import xmltodict


class Response:

    def __init__(self, status_code=200, text='', headers={}, json=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers
        self._json = json

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        return self._json


class BrokerBox:

    def __init__(self, app, event, processor, skip=False, **kwargs):
        self.broker_dispatcher = app.extensions['broker_dispatcher']
        self.queue = 'test'
        config = {
            'label': 'test-%s' % event,
            'queue': self.queue,
            'event': event,
            'processor': processor,
            'to_skip': skip,
        }
        config.update(kwargs)
        self.broker_dispatcher.event_handler.flush()
        self.broker_dispatcher.event_handler.append(config)
        self.event_handler = self.broker_dispatcher.event_handler
        self.event = event

    def get_messages(self):
        broker_legacy = self.broker_dispatcher.broker_legacy
        Message = broker_legacy.model.Message
        return Message.objects(queue=self.queue, status__ne='DONE').order_by('+created')


class MockRequests:

    def __init__(self):
        self.callback_response = None

    def make_default_response(self, *args, **kwargs):
        if self.callback_response:
            return self.callback_response(*args, **kwargs)
        else:
            return Response(200)

    def request(self, *args, **kwargs):
        return self.make_default_response(*args, **kwargs)

    def get(self, *args, **kwargs):
        return self.make_default_response('GET', *args, **kwargs)

    def post(self, *args, **kwargs):
        return self.make_default_response('POST', *args, **kwargs)

    def patch(self, *args, **kwargs):
        return self.make_default_response('PATCH', *args, **kwargs)

    def put(self, *args, **kwargs):
        return self.make_default_response('PUT', *args, **kwargs)

    def delete(self, *args, **kwargs):
        return self.make_default_response('DELETE', *args, **kwargs)


def assert_xml_payloads(xml1, xml2, fields=None, pop_count=0):
    xml1 = xmltodict.parse(xml1)
    xml2 = xmltodict.parse(xml2)
    for _ in range(pop_count):
        xml1 = xml1.popitem()[1]
        xml2 = xml2.popitem()[1]
    if not fields:
        assert xml1 == xml2
    else:
        bads_xml1 = {}
        bads_xml2 = {}
        for field in fields:
            if field not in xml1 and field not in xml2:
                continue
            if xml1.get(field) != xml2.get(field):
                if field in xml1:
                    bads_xml1[field] = xml1[field]
                if field in xml2:
                    bads_xml2[field] = xml2[field]
        assert bads_xml1 == bads_xml2


def _mock_fne_query(nom=None, prenom=None, sexe=None, date_naissance=None, nationalite=None,
                    commune_naissance=None, identifiant_agdref=None):
    if not nom and not prenom and not sexe:
        return {}
    return {
        'identifiant_agdref': identifiant_agdref or 'identifiant_agdref',
        'identifiant_portail_agdref': 'identifiant_asile',
        'nom': nom or 'nom',
        'nom_usage': 'nomUsage',
        'prenoms': prenom or 'prenom',
        'date_naissance': date_naissance.strftime('%Y%m%d')
        if date_naissance else datetime(1970, 1, 1),
        'ville_naissance': commune_naissance or 'communeNaissance',
        'pays_naissance': 'paysNaissance',
        'nationalite': nationalite or 'ZZZ',
        'sexe': sexe or 'M',
        'nom_pere': 'nomPere',
        'prenom_pere': 'prenomPere',
        'nom_mere': 'nomMere',
        'prenom_mere': 'prenomMere',
        'date_entree_en_france': datetime(1980, 2, 2),
        'date_enregistrement_agdref': datetime(1980, 3, 3),
        'localisations': {
            'adresse': {
                'numero_voie': '1',
                'codeVoie': 'codeVoie',
                'voie': 'rue',
                'chez': 'chez',
                'code_postal': '75001',
                'ville': 'PARIS',
                'code_insee': '75101'
            },
                    'organisme_origine': 'AGDREF'
        },
                'numeroDossier': 'numeroDossier',
        'codeDepartement': '75',
        'codeSousPrefectureIPREF': 'codeSousPrefectureIPREF',
        'codeStatutJuridique': 'codeStatutJuridique',
        'typeTitreActuel': 'typeTitreActuel',
        'numeroDuplicata': 'numeroDuplicata',
        'dateDebutValiditeTitreActuel': datetime(1980, 4, 4),
        'dateFinValiditeTitreActuel': datetime(1980, 5, 5),
        'referenceReglementaire': 'referenceReglementaire',
        'codeMouvement': 'codeMouvement',
        'indicateurArchivage': 'indicateurArchivage',
        'indicateurAlias': 'indicateurAlias',
        'numeroEtrangerReference': 'numeroEtrangerReference',
        'indicateurPresenceDemandeAsile': 'indicateurPresenceDemandeAsile',
        'typeTitreDemande': 'typeTitreDemande',
        'dateDebutValiditeTitreAttenteRemise': datetime(1980, 6, 6),
        'dateFinValiditeTitreAttenteRemise': datetime(1980, 7, 7),
        'libelleGenreMesureAdministrative': 'libelleGenreMesureAdministrative',
        'libelleMesureAdministrative': 'libelleMesureAdministrative'
    }


class MockFNELookup:
    """Replace the lookup_fne function with a mock that returns a predefined value.
    The mock has to be applied to the functions FNELookup.query and lookup_fne, even though
    lookup_fne points to FNELookup.query.

    The class can be used directly by instanciating it and calling ``start()`` to apply the mock,
    and ``stop()`` to deapply it.

    >>> mock = MockFNELookup()
    >>> mock.start() # lookup_fne is replaced from now on
    >>> lookup_fne() # calls the mock
    >>> mock.stop() # lookup_fne is back to its original form

    It can also be used as a context manager.
    >>> with MockFNELookup():
    >>>     lookup_fne() # calls the mock

    Be warned that the functions replaced are the ones in ``services.fne``. If you imported
    the function in your local scope, it will not be replaced.
    >>> import services
    >>> services.fne.lookup_fne() # good, the function will be replaced by the mock

    >>> from services.fne import lookup_fne
    >>> lookup_fne() # the function was imported into local space before the replacement occured,
                     # t will not be replaced.

    See http://stackoverflow.com/questions/38902714/why-does-the-behavior-of-the-patch-library-change-depending-on-how-values-are-im
    and https://docs.python.org/3/library/unittest.mock.html#id5
    """

    def __init__(self):
        self.mock_query_patcher = patch('services.fne.FNELookup.query', side_effect=_mock_fne_query)
        self.mock_lookup_patcher = patch('services.fne.lookup_fne', side_effect=_mock_fne_query)

    def start(self):
        self.mock_lookup_patcher.start()
        self.mock_query_patcher.start()

    def stop(self):
        self.mock_lookup_patcher.stop()
        self.mock_query_patcher.stop()

    def __enter__(self):
        self.start()

    def __exit__(self, type, value, traceback):
        self.stop()
