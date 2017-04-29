from datetime import datetime
import unicodedata
import xmltodict
import re
from dateutil.parser import parse as dateutil_parse

from connector.exceptions import (
    ProcessMessageNoResponseError, ProcessMessageSkippedError,
    ProcessServerNotifyRetryError)
from connector.agdref.translations import voie_trans
from connector.tools import request_logger, strip_namespaces


def from_date_to_datetime(date, delta=None):
    if not date:
        return None
    if isinstance(date, datetime):
        parsed = date
    else:
        try:
            parsed = dateutil_parse(date)
        except:
            return None
    if delta:
        parsed += delta
    return parsed


def format_date(date, delta=None):
    parsed = from_date_to_datetime(date, delta)
    if not parsed:
        parsed = ''
    return parsed.strftime("%Y%m%d")


def format_text(txt, max=None, allowed_pattern=None, transform=None):
    if not txt:
        return ''
    else:
        if transform:
            output = transform(txt)
        else:
            output = txt
        output = unicodedata.normalize('NFKD', output).encode(
            'ascii', 'ignore').decode().upper()
        if max:
            output = output[:max]
        if allowed_pattern:
            return ''.join([c if re.match(allowed_pattern, c) else ' ' for c in output])
        else:
            return output


def format_bool(boolean):
    return 'N' if not boolean else 'O'


def format_address(address):
    xml = []
    if not address:
        return xml
    for field_agdref, field_pf in (('chez', 'chez'),
                                   ('numeroVoie', 'numero_voie'), ('codePostal', 'code_postal'),
                                   ('libelleCommune', 'ville'), ('codeINSEE', 'code_insee')):
        value = address.get(field_pf)
        if value:
            xml.append('<maj:{field}>{value}</maj:{field}>'.format(
                field=field_agdref, value=format_text(value)))
    voie = format_text(address.get('voie'))
    if voie:
        xml.append('<maj:typeVoie>%s</maj:typeVoie>' %
                   voie_trans.translate_out(voie.split(' ', 1)[0]))
        xml.append('<maj:libelleVoie>%s</maj:libelleVoie>' % ' '.join(voie.split(' ', 1)[1:]))
    return xml


def format_demande(da, complement_reexamen=False):
    xml = []
    if not da:
        return xml
    # type_demande = da.get('type_demande')
    # if type_demande == 'REEXAMEN':
    #     xml.append('<maj:TypeDemande>RX</maj:TypeDemande>')
    #     xml.append(
    #         '<maj:NumeroReexamen>{:0>2}</maj:NumeroReexamen>'.format(da.get('numero_reexamen')))
    #     if complement_reexamen:

    #         if 'date_instruction_ofpra' in da:
    #             xml.append('<maj:dateAROFPRA>%s</maj:dateAROFPRA>' %
    #                        format_date(da.get('date_instruction_ofpra')))
    #         if 'date_introduction_ofpra' in da:
    #             date = from_date_to_datetime(da.get('date_introduction_ofpra'))
    #             xml.append('<maj:heureEnregistrement>{:0>2}</maj:heureEnregistrement>'.format(
    #                        date.hour))
    #             xml.append('<maj:minureEnregistrement>{:0>2}</maj:minureEnregistrement>'.format(
    #                        date.minute))
    # elif type_demande == 'REOUVERTURE':
    #     xml.append('<maj:TypeDemande>RO</maj:TypeDemande>')
    # else:
    #     xml.append('<maj:TypeDemande>PM</maj:TypeDemande>')
    return xml


def format_nombre_demande(usager):
    """
        Retrieve the number of demande asile open for a user.

        Value by default is 01 not 00
        Value is not increment in case of reouverture, it will only be increment if
        some reexamen are found
    """
    from connector.agdref.agdref_input import AgdrefBackendResponseError
    from connector.agdref import connector_agdref
    identifiant_agdref = usager.get('identifiant_agdref')
    route = '/recueils_da?q=*:*&fq=usagers_identifiant_agdref:%s' % identifiant_agdref
    try:
        r = connector_agdref.backend_requests.get(route)
    except ProcessMessageNoResponseError:
        raise AgdrefBackendResponseError()
    if r.status_code != 200:
        raise AgdrefBackendResponseError()
    # recueils_da = r.json().get('_items', [])
    # usager_recueil = retrieve_last_demande_for_given_usager(
    #     recueils_da, identifiant_agdref, usager.get('id', None))

    nombre_demande = 1
    # if usager_recueil and usager_recueil['type_demande'] == 'REEXAMEN':
    #     nombre_demande += int(usager_recueil['numero_reexamen'])
    nombre_demande = '{:0>2}'.format(nombre_demande)
    return nombre_demande


def format_date_decision(usager):
    """
        Retrieve the number of demande asile open for a user.

        Value by default is 01 not 00
        Value is not increment in case of reouverture, it will only be increment if
        some reexamen are found
    """
    from connector.agdref.agdref_input import AgdrefBackendResponseError
    from connector.agdref import connector_agdref
    identifiant_agdref = usager.get('identifiant_agdref')
    route = '/demandes_asile?q=*:*&fq=usager_identifiant_agdref:%s' % identifiant_agdref
    try:
        r = connector_agdref.backend_requests.get(route)
    except ProcessMessageNoResponseError:
        raise AgdrefBackendResponseError()
    demandes_asile = r.json().get('_items', [])
    xml = []
    if not demandes_asile:
        return xml

    def sorted_key(da):
        return da['_created']
    demandes_asile = sorted(demandes_asile, key=sorted_key, reverse=True)

    if len(demandes_asile) > 1:
        if not 'decisions_definitive' in demandes_asile[1]:
            return xml
        xml.append('<maj:DateDerniereDecision>%s<maj:DateDerniereDecision>' %
                   format_date(demandes_asile[1]['decisions_definitives'][-1]['date']))
    return xml


class AGDREFProcessor:

    BASE_NAME = None

    def __init__(self, connector):
        assert self.BASE_NAME, 'BASE_NAME is mandatory'
        self.connector = connector
        self.disabled = False

    @property
    def source(self):
        return self.BASE_NAME + 'Request'

    @property
    def reponse(self):
        return self.BASE_NAME + 'Response'

    def __call__(self, handler, msg):
        return self.query(handler, msg)

    @staticmethod
    def footer(name):
        xml = []
        xml.append('</maj:%s>' % name)
        xml.append('</soap:Body></soap:Envelope>')
        return xml

    @staticmethod
    def headers(name, flux):
        xml = []
        ts = datetime.utcnow()
        xml.append('<?xml version="1.0" encoding="UTF-8"?>'
                   '<soap:Envelope '
                   'xmlns:soap="http://www.w3.org/2003/05/soap-envelope"'
                   ' xmlns:maj="http://interieur.gouv.fr/asile/maj">')
        xml.append('<soap:Header/><soap:Body>')
        xml.append('<maj:%s>' % name)
        xml.append('<maj:typeFlux>%s</maj:typeFlux>' % flux)
        xml.append('<maj:dateEmissionFlux>%s</maj:dateEmissionFlux>' %
                   ts.strftime("%Y%m%d"))
        xml.append('<maj:heureEmissionFlux>%s</maj:heureEmissionFlux>' %
                   ts.strftime("%H%M%S"))
        return xml

    def _parse(self, req_body, msg):
        try:
            raw = xmltodict.parse(msg)
        except Exception:
            RuntimeError(
                "Le serveur distant AGDREF a renvoyé un message non valide, veuillez rejouer le message")
        # Remove soap_enveloppe
        raw = raw.popitem()[1]
        raw = raw.popitem()[1]
        raw = raw.popitem()[1]
        raw = strip_namespaces(raw)

        if raw.get('codeErreur') in ('100', '102', '500'):
            raise ProcessServerNotifyRetryError()
        if raw.get('codeErreur') != '000':
            # Change exception to Process Message Exception
            raise RuntimeError(
                "Le serveur distant AGDREF a renvoyé une erreur %s" % raw.get('codeErreur'))

    def _submit_query(self, xml, logger):
        if xml is None:
            raise RuntimeError('Aucun XML n\'a été généré')
        # agdref_request already handle no response or not available errors
        req = self.connector.agdref_request(data=xml.encode('utf8'))
        return req

    @request_logger
    def query(self, handler, msg, logger):
        if handler.to_skip:
            raise ProcessMessageSkippedError()
        if self.connector._fake_on_dna:  # TODO: remove me !
            usager = msg.context.get('usager')
            recueil_da = msg.context.get('recueil_da')
            if ((usager and usager['nom'].endswith(' dna')) or
                    (recueil_da and recueil_da.get('usager_1', {}).get('nom', '').endswith(' dna'))):
                return 'Fake DN@ usager'
        if self.connector.disabled:
            raise ProcessMessageNoResponseError('Connecteur AGDREF Désactivé')
        xml = self._build_xml(msg)
        logger.set_request(xml)
        req = self._submit_query(xml, logger)
        logger.set_response(req)
        self._parse(xml, req.text)
