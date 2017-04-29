from xmltodict import parse
import requests

from connector.processor import register_processor
from connector.exceptions import ProcessMessageNoResponseError
from connector.dna.common import (
    build_demandes_xml, build_majda_xml, DoNotSendError)
from connector.tools import request_logger
from connector.common import ConnectorException, connectors_config
from connector.tools import to_list, strip_namespaces
from connector.dna.common import dna_config


def process_response(handler, response):
    dico = strip_namespaces(parse(response))
    dico = dico.popitem()[1]

    try:
        tmp = dico['Body']['getDonneePortailResponse']['REPONSES']
    except KeyError:
        tmp = dico['Body']['majDonneesDAResponse'].get('REPONSES', False)
    if tmp:
        dico = tmp['REPONSE']
    else:
        if tmp is False:
            raise ConnectorException(37, "Invalid Response")
        return

    if not dico:
        raise ConnectorException(38, "Invalid Response")
    dico = to_list(dico)
    for reponse in dico:
        code_erreur = reponse.get('CODE_ERREUR')
        if code_erreur and code_erreur != '00':
            raise ConnectorException(reponse['CODE_ERREUR'], reponse.get('LIBELLE_ERREUR'))
        identifiant_famille_dna = reponse.get('ID_FAMILLE_DNA')
        id_recueil = reponse.get('ID_RECUEIL_DEMANDE')
        usagers = reponse.get('USAGERS')
        if usagers:
            usagers = usagers.get('USAGER')
            usagers = to_list(usagers)
            for usager in usagers:
                id_usager = usager.get('ID_USAGER_PORTAIL')
                identifiant_dna = usager.get('ID_DNA')
                # Perform request to backend
                payload = {"identifiant_dna": identifiant_dna,
                           "identifiant_famille_dna": identifiant_famille_dna}
                route = '%s/usagers/%s' % (connectors_config.server, id_usager)
                r = dna_config.requests.patch(
                    route, json=payload, auth=(dna_config.user, dna_config.password))
                if r.status_code != 200:
                    raise ConnectorException(r.status_code, r.text)
        elif handler.event == "recueil_da.pa_realise":
            # get recueil
            if not identifiant_famille_dna:
                raise ConnectorException(reponse['CODE_ERREUR'], 'Identifiant Famille DNA non reçu')
            route = "%s/recueils_da/%s/enregistrement_famille_ofii" % (
                connectors_config.server, id_recueil)
            payload = {}
            payload['identifiant_famille_dna'] = identifiant_famille_dna
            # put everything
            r = dna_config.requests.post(
                route, auth=(dna_config.user, dna_config.password), json=payload)
            if not r.ok:
                raise ConnectorException(r.status_code, r.text)


@register_processor
@request_logger
def dna_recuperer_donnees_portail(handler, msg, logger):
    if msg.context.get('recueil_da', {}).get('profil_demande') == 'MINEUR_ISOLE':
        return 'Pas de demande pour MINEUR_ISOLE.'
    if msg.context.get('recueil_da', {}).get('profil_demande') == 'MINEUR_ACCOMPAGNANT':
        if not (msg.context.get('recueil_da', {}).get('usager_1', {}).get("demandeur") or
                msg.context.get('recueil_da', {}).get('usager_2', {}).get("demandeur")):
            return 'Pas de demande pour MINEUR_ACCOMPAGNANT sans parent demandeur.'
    try:
        xml = build_demandes_xml(handler, msg)
    except DoNotSendError as exc:
        return str(exc)
    logger.set_request(xml)
    try:
        req = dna_config.requests.post(dna_config.url + "/getDonneesPortail",
                                       data=xml.encode(), proxies=dna_config.proxies)
    except requests.ConnectionError as exc:
        raise ProcessMessageNoResponseError(exc)
    logger.set_response(req)
    if req.status_code != 200:
        raise ConnectorException(req.status_code, req.text)
    else:
        process_response(handler, req.text)


@register_processor
@request_logger
def dna_recuperer_donnees_portail_by_step(handler, msg, logger):
    if msg.context.get('recueil_da', {}).get('profil_demande') == 'MINEUR_ISOLE':
        return 'Pas de demande pour MINEUR_ISOLE.'
    if msg.context.get('recueil_da', {}).get('profil_demande') == 'MINEUR_ACCOMPAGNANT':
        if not (msg.context.get('recueil_da', {}).get('usager_1', {}).get("demandeur") or
                msg.context.get('recueil_da', {}).get('usager_2', {}).get("demandeur")):
            return 'Pas de demande pour MINEUR_ACCOMPAGNANT sans parent demandeur.'
    for _event in ['recueil_da.pa_realise', 'recueil_da.exploite']:
        handler.event = _event
        try:
            xml = build_demandes_xml(handler, msg)
        except DoNotSendError as e:
            return str(e)
        logger.set_request(xml)
        try:
            req = dna_config.requests.post(dna_config.url + "/getDonneesPortail",
                                           data=xml.encode(), proxies=dna_config.proxies)
        except ConnectionError as e:
            raise ProcessMessageNoResponseError(e)
        logger.set_response(req)
        if req.status_code != 200:
            raise ConnectorException(req.status_code, req.text)
        else:
            process_response(handler, req.text)


@register_processor
@request_logger
def dna_majda(handler, msg, logger):
    try:
        xml = build_majda_xml(handler, msg)
    except DoNotSendError as exc:
        return str(exc)
    logger.set_request(xml)
    try:
        req = dna_config.requests.post(
            dna_config.url + "/majDonneesDA", data=xml.encode(), proxies=dna_config.proxies)
    except requests.ConnectionError as exc:
        raise ProcessMessageNoResponseError(exc)
    logger.set_response(req)
    if req.status_code != 200:
        raise ConnectorException(req.status_code, req.text)
    else:
        process_response(handler, req.text)
