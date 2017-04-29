from flask import request, Response
from flask.ext.restful import Resource
from datetime import datetime
import xmltodict

from connector.tools import strip_namespaces
from connector.agdref.translations import voie_trans, pays_trans
from connector.debugger import debug
from connector.exceptions import ProcessMessageNoResponseError


class AgdrefInputError(Exception):
    code = 1


class AgdrefMissingFieldError(AgdrefInputError):
    code = 2


class AgdrefBackendResponseError(AgdrefInputError):
    code = 3


class AgdrefBadIntError(AgdrefInputError):
    code = 4


class AgdrefBadBoolError(AgdrefInputError):
    code = 5


class AgdrefBadDateError(AgdrefInputError):
    code = 6


class AgdrefUnknownUsagerError(AgdrefInputError):
    code = 7


class AgdrefInvalidBodyError(AgdrefInputError):
    code = 8


class AgdrefNotImplementedError(AgdrefInputError):
    code = 501


def _forge_response(agdref_id='', portail_id='', da_id='', ret='0'):
    ts = datetime.utcnow()
    xml = []
    xml.append('<?xml version="1.0" encoding="UTF-8"?>'
               '<soapenv:Envelope '
               'xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"'
               ' xmlns:asil="http://interieur.gouv.fr/asile/">')
    xml.append('<asil:SIAsileResponse>')
    xml.append('<asil:Tracability>')
    xml.append('<typeFlux>11</typeFlux>')
    xml.append('<dateFlux>%s</dateFlux>' % ts.strftime("%Y%m%d"))
    xml.append('<heureFlux>%s</heureFlux>' % ts.strftime("%H%M%S"))
    xml.append('<numeroEtranger>%s</numeroEtranger>' % agdref_id)
    xml.append('<identifiantSIAsile>%s</identifiantSIAsile>' % portail_id)
    xml.append('<numeroDemandeAsile>%s</numeroDemandeAsile>' % da_id)
    xml.append('</asil:Tracability>')

    xml.append('<asil:Identifier>')
    xml.append('<codeRetourSIAsile>{:0>3}</codeRetourSIAsile>'.format(ret))
    xml.append('<datePriseEnCompteSIAsile>%s</datePriseEnCompteSIAsile>' %
               ts.strftime("%Y%m%d"))
    xml.append('<heurePriseEnCompteSIAsile>%s</heurePriseEnCompteSIAsile>' %
               ts.strftime("%H%M%S"))
    xml.append('</asil:Identifier>')
    xml.append('</asil:SIAsileResponse>')
    xml.append('</soapenv:Envelope>')
    return ''.join(xml)


def _remove_envelope(msg):
    raw = xmltodict.parse(msg)
    # Remove soap_enveloppe
    raw = raw.popitem()[1]
    raw = raw.popitem()[1]
    raw = strip_namespaces(raw)
    cmd, raw = raw.popitem()
    try:
        tracability = raw['Tracability']
        payload = raw['Identifier']
        agdref_id = tracability['numeroEtranger']
        portail_id = tracability['identifiantSIAsile']
        da_id = tracability['numeroDemandeAsile']
    except KeyError:
        raise AgdrefInvalidBodyError()
    return cmd, agdref_id, portail_id, da_id, payload


def _retrieve_usager(agdref_id):
    from connector.agdref import connector_agdref
    # Retrieve usager id in the backend
    try:
        r = connector_agdref.backend_requests.get(
            '/usagers/%s?par_identifiant_agdref=true' % agdref_id)
    except ProcessMessageNoResponseError:
        raise AgdrefBackendResponseError()
    if r.status_code == 404:
        raise AgdrefUnknownUsagerError()
    elif r.status_code != 200:
        raise AgdrefBackendResponseError()
    return r.json()


def _parse_bool(value, required=False):
    if value in (None, ''):
        if required:
            raise AgdrefMissingFieldError()
        return None
    if value == 'O':
        return True
    elif value == 'N':
        return False
    else:
        raise AgdrefBadBoolError()


def _parse_int(value, required=False):
    if value in (None, ''):
        if required:
            raise AgdrefMissingFieldError()
        return None
    try:
        return int(value)
    except ValueError:
        raise AgdrefBadIntError()


def _parse_date(value, required=False, isoformat=True):
    if value in (None, ''):
        if required:
            raise AgdrefMissingFieldError()
        return None
    try:
        date = datetime.strptime(value, '%Y%m%d')
        if isoformat:
            return date.isoformat()
        else:
            return date
    except ValueError:
        raise AgdrefBadDateError()


def procedure_eloignement(connector_agdref, usager, msg):
    route = usager['_links']['update']
    eloignement = {
        'delai_depart_volontaire': _parse_int(msg.get('delaiDepartVolontaire')),
        'execution': _parse_bool(msg.get('executionMesure')),
        'date_decision': _parse_date(msg.get('dateDecisionEloignement')),
        'date_execution': _parse_date(msg.get('dateExecutionEloignement')),
        'contentieux': _parse_bool(msg.get('contentieux')),
        'decision_contentieux': msg.get('decisionContentieux')
    }
    eloignement = {f: v for f, v in eloignement.items() if v is not None}
    if not eloignement:
        raise AgdrefMissingFieldError()
    try:
        r = connector_agdref.backend_requests.patch(route, json={
            'eloignement': eloignement
        })
    except ProcessMessageNoResponseError:
        raise AgdrefBackendResponseError()
    if r.status_code != 200:
        raise AgdrefBackendResponseError()


def mise_a_jour_adresse(connector_agdref, usager, msg):
    loc = {}
    adresse = {}
    adresse['chez'] = msg.get('chez')
    adresse['numero_voie'] = msg.get('numeroVoie')
    voie = ''
    if msg.get('typeVoie'):
        voie = voie_trans.translate_in(msg.get('typeVoie'))
        if not voie:
            voie = msg.get('typeVoie') + ' '
        else:
            voie = voie.upper() + ' '
    voie += msg.get('libelleVoie', '') or ''
    adresse['voie'] = voie
    adresse['code_postal'] = msg.get('codePostal')
    adresse['ville'] = msg.get('libelleCommune')

    loc['date_maj'] = _parse_date(msg.get('dateMAJ'), required=True)
    loc['organisme_origine'] = 'AGDREF'
    adresse = {f: v for f, v in adresse.items() if v}
    loc['adresse'] = adresse
    loc = {f: v for f, v in loc.items() if v}
    route = usager['_links']['localisations']
    try:
        r = connector_agdref.backend_requests.post(route, json=loc)
    except ProcessMessageNoResponseError:
        raise AgdrefBackendResponseError()
    if r.status_code != 200:
        raise AgdrefBackendResponseError()


def procedure_naturalisation(connector_agdref, usager, msg):
    naturalisation = _parse_date(msg.get('dateNaturalisation'), required=True)
    if not naturalisation:
        raise AgdrefMissingFieldError()
    route = usager['_links']['update']
    try:
        r = connector_agdref.backend_requests.patch(route, json={
            'date_naturalisation': naturalisation
        })
    except ProcessMessageNoResponseError:
        raise AgdrefBackendResponseError()
    if r.status_code != 200:
        raise AgdrefBackendResponseError()


def procedure_readmission(connector_agdref, da_id, msg):
    payload = {
        'date_demande_EM': _parse_date(msg.get('dateDemandealEtatMembre'), required=True),
        'EM': pays_trans.translate_in(msg.get('etatMembre')),
        'date_reponse_EM': _parse_date(msg.get('dateReponseEtatMembre')),
        'reponse_EM': msg.get('reponseEtatMembre'),
        'date_decision': _parse_date(msg.get('dateDecisionOuTransfert')),
        'date_execution': _parse_date(msg.get('dateExecutionTransfert')),
        'execution': _parse_bool(msg.get('executionMesure')),
        'delai_depart_volontaire': msg.get('delaiDepartVolontaire'),
        'contentieux': _parse_bool(msg.get('contentieux')),
        'decision_contentieux': msg.get('decisionContentieux')
    }
    payload = {f: v for f, v in payload.items() if v is not None}
    route = '/demandes_asile/%s/dublin' % da_id
    try:
        r = connector_agdref.backend_requests.patch(route, json=payload)
    except ProcessMessageNoResponseError:
        raise AgdrefBackendResponseError()
    if r.status_code != 200:
        raise AgdrefBackendResponseError()


def delivrance_document_sejour(connector_agdref, da_id, usager, msg):
    # raise AgdrefNotImplementedError()
    payload_support = {
        'date_delivrance': _parse_date(msg.get('dateDelivrance'), required=True),
        'lieu_delivrance': _parse_date(msg.get('lieuDelivrance'), required=True),
        '???': msg.get('referenceReglementaire'),  # TODO
    }
    payload = {
        'usager': usager['id'],
        "demande_origine": {'id': da_id, '_cls': 'DemandeAsile'},
        'type_document': msg.get('typeDocument'),
        # '': msg.get('dureeValiditeDocument'),  #  TODO: useful ?
        'date_debut_validite': _parse_date(msg.get('dateDebutValidite'), required=True),
        'date_fin_validite': _parse_date(msg.get('dateFinValidite'), required=True),
        'date_retrait_attestation': _parse_date(msg.get('dateRetraitDocument')),
    }
    try:
        r = connector_agdref.backend_requests.post('/droits', json=payload)
    except ProcessMessageNoResponseError:
        raise AgdrefBackendResponseError()
    if r.status_code != 200:
        raise AgdrefBackendResponseError()
    try:
        r = connector_agdref.backend_requests.post(
            '/droits/%s/supports', json=payload_support)
    except ProcessMessageNoResponseError:
        raise AgdrefBackendResponseError()
    if r.status_code != 200:
        raise AgdrefBackendResponseError()


def enregistrement_retrait_document_asile(connector_agdref, usager, msg):
    raise AgdrefNotImplementedError()


def maj_agdref(xml):
    from connector.agdref import connector_agdref
    cmd, agdref_id, portail_id, da_id, msg = _remove_envelope(xml)
    try:
        usager = _retrieve_usager(agdref_id)
        if cmd == 'procedureEloignementRequest':
            procedure_eloignement(connector_agdref, usager, msg)
        elif cmd == 'procedureReadmissionRequest':
            procedure_readmission(connector_agdref, da_id, msg)
        elif cmd == 'delivranceDocumentSejourRequest':
            delivrance_document_sejour(connector_agdref, da_id, usager, msg)
        elif cmd == 'enregistrementNaturalisationRequest':
            procedure_naturalisation(connector_agdref, usager, msg)
        elif cmd == 'enregistrementRetraitDocumentAsileRequest':
            enregistrement_retrait_document_asile(connector_agdref, usager, msg)
        elif cmd == 'miseAJourAdresseRequest':
            mise_a_jour_adresse(connector_agdref, usager, msg)
    except AgdrefInputError as exc:
        return _forge_response(agdref_id, portail_id, da_id, exc.code)
    return _forge_response(agdref_id, portail_id, da_id)


class MajAGDREF(Resource):

    @debug
    def post(self):
        from connector.agdref import connector_agdref
        if connector_agdref.disabled_input:
            return Response('Connecteur AGDREF entrant désactivé', status=503, mimetype='text/xml')
        xml = request.get_data()
        response = maj_agdref(xml)
        return Response(response, mimetype='text/xml')

    def get(self):
        from connector.agdref import connector_agdref
        with open('connector/agdref/static/MiseAJourAGDREF.wsdl', 'r') as f:
            return Response(f.read().format(connector_agdref.exp_url), mimetype='text/xml')
