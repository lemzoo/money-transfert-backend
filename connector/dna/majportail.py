from flask import Response, request
from xmltodict import parse
from flask.ext.restful import Resource
from datetime import datetime
from dateutil.parser import parse as date_parse

from connector.tools import to_list, strip_namespaces, check_bool
from connector.dna.common import dna_config
from connector.debugger import debug


def check_date(date=None):
    if not date or date == '':
        return False
    try:
        date_parse(date)
    except:
        return False
    return True


def returnMAJ(errcode, msg="Erreur Survenue"):
    reponse = []
    reponse.append('<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
                   'xmlns:tns="http://service.webservices.dna.anaem.social.fr/MajPortailService">'
                   '<soapenv:Header/>'
                   '<soapenv:Body>'
                   '<tns:majPortailResponse>'
                   '<tns:CODE_ERREUR>')
    if errcode == 0:
        reponse.append('0')
        reponse.append('</tns:CODE_ERREUR><tns:LIBELLE_ERREUR />')

    else:
        reponse.append(str(errcode))
        reponse.append('</tns:CODE_ERREUR>')
        reponse.append('<tns:LIBELLE_ERREUR>%s</tns:LIBELLE_ERREUR>' % msg)

    reponse.append('</tns:majPortailResponse></soapenv:Body></soapenv:Envelope>')
    return ''.join(reponse)


def dna_maj_portail(xml):
    # Parse the wsdl
    try:
        dico = strip_namespaces(parse(xml))
        # Remove soap_enveloppe
        try:
            dico = dico['Envelope']['Body']['MajPortail']['MAJPORTAIL']
        except KeyError:
            dico = dico['Envelope']['Body']['majPortail']['MAJPORTAIL']
    except Exception as exc:
        return returnMAJ(1, "Le message n'a pu être parsé (%s)" % exc)

    individus = dico.get('INDIVIDUS')
    if not individus:
        return returnMAJ(2, "Balise INDIVIDUS manquante")
    individus = individus.get('INDIVIDU')
    if not individus:
        return returnMAJ(12, "Au moins une balise INDIVIDU doit etre présente")
    individus = to_list(individus)
    for individu in individus:
        usager = {}
        demande_asile = {}
        try:
            usager_id = int(individu.get('ID_USAGER_PORTAIL'))
        except (ValueError, TypeError):
            return returnMAJ(7, 'ID_USAGER_PORTAIL invalide')
        if not usager_id:
            return returnMAJ(7, 'ID_USAGER_PORTAIL manquant')
        id_recueil = individu.get('ID_RECUEIL_DEMANDE')
        if not id_recueil:
            return returnMAJ(8, 'ID_RECUEIL manquant')
        opc = individu.get('OPC')
        if opc:
            opc_accepte = {'acceptation_opc': check_bool(opc['OPC_ACCEPTE'])}
        else:
            opc_accepte = None
        vulnerabilite = individu.get('VULNERABILITE')
        if vulnerabilite:
            usager['vulnerabilite'] = {}
            # safety check
            for vuln, value in vulnerabilite.items():
                if vuln not in ('VULNERABLE', 'ENCEINTE', 'ENCEINTE_DATE_TERME', 'MALVOYANTE',
                                'MALENTENDANTE', 'INTERPRETE_SIGNE', 'MOBILITE_REDUITE',
                                'INDISPONIBILITE_POTENTIELLE'):
                    return returnMAJ(11, "Vulnérabilité inconnue : %s" % vuln)

            # get values
            if vulnerabilite.get('ENCEINTE'):
                usager['vulnerabilite']['grossesse'] = check_bool(vulnerabilite.get('ENCEINTE'))
                if usager['vulnerabilite']['grossesse']:
                    usager['vulnerabilite']['grossesse_date_terme'] = vulnerabilite.get(
                        'ENCEINTE_DATE_TERME', '')
            if vulnerabilite.get('VULNERABLE'):
                usager['vulnerabilite']['objective'] = check_bool(vulnerabilite.get('VULNERABLE'))
            if vulnerabilite.get('MALVOYANTE'):
                usager['vulnerabilite']['malvoyance'] = check_bool(vulnerabilite.get('MALVOYANTE'))
            if vulnerabilite.get('MALENTENDANTE'):
                usager['vulnerabilite']['malentendance'] = check_bool(vulnerabilite.get(
                    'MALENTENDANTE'))
            if vulnerabilite.get('INTERPRETE_SIGNE'):
                usager['vulnerabilite']['interprete_signe'] = check_bool(vulnerabilite.get(
                    'INTERPRETE_SIGNE'))
            if vulnerabilite.get('MOBILITE_REDUITE'):
                usager['vulnerabilite']['mobilite_reduite'] = check_bool(vulnerabilite.get(
                    'MOBILITE_REDUITE'))

        orientation = individu.get('ORIENTATION')
        if orientation:
            demande_asile['agent_orientation'] = orientation.get('AGENT_OFII')
            date = orientation.get('DATE_SAISIE')
            if not check_date(date):
                return returnMAJ(13, 'Mauvais format de date : "%s"' % date)
            demande_asile['date_orientation'] = date

        hebergement = individu.get('HEBERGEMENT')
        if hebergement:
            demande_asile['hebergement'] = {}
            if hebergement.get('TYPE_HEBERGEMENT') == 'Hébergement temporaire':
                demande_asile['hebergement']['type'] = 'HUDA'
            if hebergement.get('TYPE_HEBERGEMENT') == 'Hébergement pérenne':
                demande_asile['hebergement']['type'] = 'CADA'
            if hebergement.get('DATE_ENTREE'):
                date = hebergement.get('DATE_ENTREE')
                if not check_date(date):
                    return returnMAJ(13, 'Mauvais format de date : "%s"' % date)
                demande_asile['hebergement'][
                    'date_entre_hebergement'] = date
            if hebergement.get('DATE_SORTIE'):
                date = hebergement.get('DATE_SORTIE')
                if not check_date(date):
                    return returnMAJ(13, 'Mauvais format de date : "%s"' % date)
                demande_asile['hebergement'][
                    'date_sortie_hebergement'] = date
            if hebergement.get('DATE_REFUS'):
                date = hebergement.get('DATE_REFUS')
                if not check_date(date):
                    return returnMAJ(13, 'Mauvais format de date : "%s"' % date)
                demande_asile['hebergement'][
                    'date_refus_hebergement'] = date

        dna_adresse = individu.get('ADRESSE')
        localisation = {}
        if dna_adresse:
            localisation['organisme_origine'] = 'DNA'
            localisation['date_maj'] = datetime.utcnow().isoformat()
            adresse = {}
            localisation['adresse'] = adresse
            for f_pf, f_dna in (('numero_voie', 'NUMERO_VOIE'),
                                ('voie', 'LIBELLE_VOIE'),
                                ('complement', 'ADRESSE2'),
                                ('code_postal', 'CODE_POSTAL'),
                                ('code_insee', 'CODE_INSEE'),
                                ('ville', 'VILLE')):
                value = dna_adresse.get(f_dna)
                if value:
                    adresse[f_pf] = value
            for f_pf, f_dna in (('telephone', 'TELEPHONE'), ('email', 'EMAIL')):
                value = dna_adresse.get(f_dna)
                if value:
                    usager[f_pf] = value
            # localisation['adresse'][''] = adresse.get('NUM_DOMICILIATION') #??

        # Post the usager_data
        if usager:
            r = dna_config.backend_requests.patch('/usagers/%s' % usager_id, json=usager)
            if not r.ok:
                return returnMAJ(3,
                                 'Données usager incorrectes : %s : %s' % (r.status_code, r.text))

        # Post address :
        if localisation:
            route = '/usagers/%s/localisations' % usager_id
            r = dna_config.backend_requests.post(route, json=localisation)
            if not r.ok:
                return returnMAJ(4, 'Adresse usager incorrecte : %s : %s' % (r.status_code, r.text))
        # Retrieve the DA and update
        if demande_asile or opc_accepte:
            # Find back the demande asile
            r = dna_config.backend_requests.get('/recueils_da/%s' % id_recueil)
            if not r.ok:
                return returnMAJ(5, "Impossible de trouver le recueil à l'origine de la demande")
            recueil = r.json()
            da_url = None
            if recueil.get('usager_1', {}).get('usager_existant', {}).get('id') == usager_id:
                da_url = recueil.get('usager_1', {}).get(
                    'demande_asile_resultante', {}).get('_links', {}).get('self')
            elif recueil.get('usager_2', {}).get('usager_existant', {}).get('id') == usager_id:
                da_url = recueil.get('usager_2', {}).get(
                    'demande_asile_resultante', {}).get('_links', {}).get('self')
            else:
                for child in recueil.get('enfants', ()):
                    if child.get('usager_existant', {}).get('id') == usager_id:
                        da_url = child.get('demande_asile_resultante', {}).get(
                            '_links', {}).get('self')
                        break
            if not da_url:
                return returnMAJ(5, 'Impossible de trouver la demande d\'asile associée')
            else:
                r = dna_config.backend_requests.get(da_url)
                if not r.ok:
                    return returnMAJ(5, 'Impossible de trouver la demande d\'asile associée')
            da = r.json()
            id_da = da.get('id')
            if demande_asile:
                if demande_asile.get('hebergement'):
                    tmp = da.get('hebergement', {})
                    tmp.update(demande_asile['hebergement'])
                    demande_asile['hebergement'] = tmp
                r = dna_config.backend_requests.post(
                    '/demandes_asile/%s/orientation' % id_da, json=demande_asile)
                if not r.ok:
                    return returnMAJ(6, "Orientation de la demande d\'asile refusée : %s : %s" % (
                        r.status_code, r.text))
            if opc_accepte:
                r = dna_config.backend_requests.patch(
                    '/demandes_asile/%s' % id_da, json=opc_accepte)
                if not r.ok:
                    return returnMAJ(14, 'Mise à jour de la demande d\'asile refusée : %s : %s' % (
                        r.status_code, r.text))
    return returnMAJ(0, 'OK')


class MajPortailAPI(Resource):

    @debug
    def post(self):
        if dna_config.disabled_input:
            return Response(returnMAJ(77, msg="Connecteur DN@ entrant désactivé"), status=503, mimetype='text/xml')
        return Response(dna_maj_portail(request.get_data()), mimetype='text/xml')

    def get(self):
        with open('connector/dna/static/wsdl.xml', 'r') as f:
            return Response(
                f.read().replace('{0}', dna_config.exp_url),
                mimetype='text/xml')


class MajPortailParams(Resource):

    def get(self):
        with open('connector/dna/static/MajPortailParams.xsd', 'r') as f:
            return Response(
                f.read().replace('{0}', dna_config.exp_url),
                mimetype='text/xml')


class MajPortailResponseParams(Resource):

    def get(self):
        with open('connector/dna/static/MajPortailResponseParams.xsd', 'r') as f:
            return Response(
                f.read().replace('{0}', dna_config.exp_url),
                mimetype='text/xml')
