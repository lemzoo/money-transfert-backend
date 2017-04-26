from dateutil.parser import parse
from requests import ConnectionError

from connector.exceptions import ProcessMessageNoResponseError
from connector.agdref.common import (
    AGDREFProcessor, format_date, format_text, format_nombre_demande)
from connector.agdref.translations import voie_trans, insee_to_libelle


def format_address(address):
    xml = []
    if not address:
        return xml
    for field_agdref, field_pf, max_size, allowed_pattern in (
            ('chez', 'chez', 21, None),
            ('numeroVoie', 'numero_voie', 4, None),
            ('codePostal', 'code_postal', 5, r"[0-9]")):
        value = address.get(field_pf)
        if value:
            xml.append('<maj:{field}>{value}</maj:{field}>'.format(
                field=field_agdref,
                value=format_text(value, max=max_size, allowed_pattern=allowed_pattern)))
    xml.append('<maj:ville>%s</maj:ville>' % insee_to_libelle(address)[:28])
    voie = format_text(address.get('voie'))
    if voie:
        xml.append('<maj:codeVoie>%s</maj:codeVoie>' %
                   voie_trans.translate_out(voie.split(' ', 1)[0])[:4])
        xml.append('<maj:rue>%s</maj:rue>' % ' '.join(voie.split(' ', 1)[1:])[:24])
    return xml


def _compute_duree_validite(delta):
    # Find the closest duration to the given delta
    DURATIONS = ((30, '0001'), (90, '0003'), (120, '0004'), (180, '0006'), (270, '0009'))
    return min(DURATIONS, key=lambda x: abs(x[0] - delta))[1]


def common_information_flux_05(context):
    usager = context['usager']
    loc = usager.get('localisation')
    adresse = loc.get('adresse') if loc else None
    xml = []
    xml.append(
        '<maj:numeroRessortissantEtranger>%s</maj:numeroRessortissantEtranger>' %
        usager.get('identifiant_agdref', ''))
    xml.append('<maj:identifiantSIAsile>%s</maj:identifiantSIAsile>' %
               usager.get('identifiant_portail_agdref', ''))
    xml.append('<maj:numeroDemandeAsile>%s</maj:numeroDemandeAsile>' %
               format_nombre_demande(usager))
    # Adresse
    xml += format_address(adresse)
    return xml


class EditionAttestationDemandeAsile(AGDREFProcessor):

    BASE_NAME = 'editionAttestionDemandeAsile'

    def _build_xml(self, msg):
        context = msg.context
        usager = context['usager']
        loc = usager.get('localisation')
        adresse = loc.get('adresse') if loc else None
        droit = context['droit']
        support = context['support']
        xml = self.headers(self.source, '05')
        xml.extend(common_information_flux_05(context))
        # Droits
        xml.append('<maj:typeDocument>ADA</maj:typeDocument>')
        # TODO
        # xml.append('<maj:typeDocument>%s</maj:typeDocument>' % droit['type_document'])
        delta = (parse(droit['date_fin_validite']) - parse(droit['date_debut_validite'])).days
        xml.append('<maj:dureeValiditeDocument>%s</maj:dureeValiditeDocument>' %
                   _compute_duree_validite(delta))
        xml.append('<maj:dateDebutValidite>%s</maj:dateDebutValidite>' %
                   format_date(droit['date_debut_validite']))
        xml.append('<maj:dateFinValidite>%s</maj:dateFinValidite>' %
                   format_date(droit['date_fin_validite']))
        xml.append('<maj:lieuDelivranceDocument>1</maj:lieuDelivranceDocument>')
        # Get back the prefecture to get the departement
        try:
            url = support['lieu_delivrance']['_links']['self']
            r = self.connector.backend_requests.get(url)
            if r.status_code != 200:
                raise RuntimeError('Requête backend %s : erreur %s\n%s' %
                                   (url, r.status_code, r.text))
            json = r.json()
            code_departement = json.get('code_departement')
            if not code_departement and 'autorite_rattachement' in json:
                url = r.json()['autorite_rattachement']['_links']['self']
                r = self.connector.backend_requests.get(url)
                if r.status_code != 200:
                    raise RuntimeError('Requête backend %s : erreur %s\n%s' %
                                       (url, r.status_code, r.text))
                code_departement = r.json().get('code_departement')
        except ConnectionError as e:
            raise ProcessMessageNoResponseError("%s\n\nPas de Réponse du backend" % e)
        xml.append('<maj:autoriteDelivranceDocument>%s</maj:autoriteDelivranceDocument>' %
                   code_departement)
        xml.append('<maj:dateDelivranceDocument>%s</maj:dateDelivranceDocument>' %
                   format_date(support['date_delivrance']))
        xml.append(
            '<maj:numeroDuplicata>{:0>2}</maj:numeroDuplicata>'.format(support['numero_duplicata']))
        xml.extend(self.footer(self.source))
        return ''.join(xml)


class EditionAttestationDemandeAsileRefus(AGDREFProcessor):

    BASE_NAME = 'editionAttestionDemandeAsile'

    def _build_xml(self, msg):
        context = msg.context
        # Retrieve the demande d'asile
        da = context['demande_asile']
        xml = self.headers(self.source, '05')
        xml.extend(common_information_flux_05(context))
        xml.append(
            '<maj:dateNotificationRefus>{}</maj:dateNotificationRefus>'.format(format_date(da['decisions_attestation'][-1]['date_decision'])))
        xml.append(
            '<maj:motifRefus>{}</maj:motifRefus>'.format(da['decisions_attestation'][-1]['motif']))
        xml.extend(self.footer(self.source))
        return ''.join(xml)
