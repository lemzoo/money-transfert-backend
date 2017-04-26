from random import choice
from string import digits, ascii_letters
import requests
from functools import partial

from connector.exceptions import ProcessMessageNoResponseError
from connector.agdref.common import (
    AGDREFProcessor, format_date, format_text, format_bool,
    format_nombre_demande, format_demande, format_date_decision)
from connector.agdref.translations import (
    nationalite_trans, pays_trans, sit_fam_trans, proc_trans,
    cond_entree_france_trans, voie_trans, origine_nom_trans, insee_to_libelle)
from sief.model.recueil_da import UsagerRecueil


def format_address(address):
    xml = []
    if not address:
        return xml
    for field_agdref, field_pf, max_size, allowed_pattern in (
            ('chez', 'chez', 21, r"[A-Za-z '.\-,]"),
            ('numeroVoie', 'numero_voie', 4, r"[A-Za-z0-9 ]"),
            ('codePostal', 'code_postal', 5, r"[0-9]")):
        value = address.get(field_pf)
        if value:
            xml.append('<maj:{field}>{value}</maj:{field}>'.format(
                field=field_agdref,
                value=format_text(value, max=max_size, allowed_pattern=allowed_pattern)))
    xml.append('<maj:ville>%s</maj:ville>' % insee_to_libelle(address)[:28])
    voie = format_text(address.get('voie'), allowed_pattern=r"[A-Za-z0-9 ,'\-]")
    if voie:
        xml.append('<maj:typeDeVoie>%s</maj:typeDeVoie>' %
                   voie_trans.translate_out(voie.split(' ', 1)[0])[:4])
        xml.append('<maj:rue>%s</maj:rue>' % ' '.join(voie.split(' ', 1)[1:])[:24])
    return xml


# Given usager can either be a dic dump or a recueil_da.UsagerRecueil, we need
# a compatibility layer

def _get(elem, field, default=''):
    if hasattr(elem, 'get'):
        value = elem.get(field)
    else:
        value = getattr(elem, field)
    return value if value not in ('', None) else default


def _get_adresse(usager):
    if isinstance(usager, dict):
        return usager.get('localisation', {}).get('adresse')
    if isinstance(usager, UsagerRecueil):
        address = usager.adresse
    else:
        address = usager.localisations[-1].adresse
    return {field: getattr(address, field, '')
            for field in ('chez', 'numero_voie', 'code_postal', 'ville', 'code_insee', 'voie')}


class DemandeNumeroOuValidationRequest(AGDREFProcessor):

    BASE_NAME = 'demandeNumeroOuValidation'

    def _build_xml(self, msg):
        context = msg.context
        da = context['demande_asile']
        usager = context['usager']
        return self.build_soap_request(usager, da, numero_da=format_nombre_demande(usager))

    def build_soap_request(self, usager, da, code_departement=None, numero_da=1):
        xml = self.headers(self.source, '03')
        xml += self._build_usager(usager, numero_da)
        # Get back the prefecture to get the departement
        if not code_departement:
            assert da, 'da cannot be empty if code_departement is not explicitely provided'
            try:
                url = da['structure_guichet_unique']['_links']['self']
                r = self.connector.backend_requests.get(url)
                if r.status_code != 200:
                    raise RuntimeError('Requête backend %s : erreur %s\n%s' %
                                       (url, r.status_code, r.text))
                url = r.json()['autorite_rattachement']['_links']['self']
                r = self.connector.backend_requests.get(url)
                if r.status_code != 200:
                    raise RuntimeError('Requête backend %s : erreur %s\n%s' %
                                       (url, r.status_code, r.text))
            except requests.ConnectionError as exc:
                raise ProcessMessageNoResponseError("%s\n\nPas de Réponse du backend" % exc)
            code_departement = r.json().get('code_departement')
        xml.append('<maj:codeDepartement>%s</maj:codeDepartement>' % code_departement)
        xml += self._build_da(da, usager)
        xml.extend(self.footer(self.source))
        return ''.join(xml)

    @staticmethod
    def _build_usager(usager, numero_da):
        xml = []
        # Create on demande identifiant_portail_agdref
        identifiant_portail_agdref = _get(usager, 'identifiant_portail_agdref')
        if not identifiant_portail_agdref:
            identifiant_portail_agdref = ''.join(choice(ascii_letters + digits) for _ in range(12))
        # Usager stuff
        xml.append('<maj:numeroRessortissantEtranger>%s</maj:numeroRessortissantEtranger>' %
                   _get(usager, 'identifiant_agdref'))
        xml.append('<maj:identifiantSIAsile>%s</maj:identifiantSIAsile>' %
                   identifiant_portail_agdref)
        xml.append('<maj:numeroDemandeAsile>{:0>2}</maj:numeroDemandeAsile>'.format(numero_da))
        format_name = partial(format_text, allowed_pattern=r"[a-zA-Z \-']")
        nom = format_name(_get(usager, 'nom'), max=44)
        xml.append('<maj:nomRessortissantEtranger>%s</maj:nomRessortissantEtranger>' % nom)
        xml.append('<maj:origineNom>%s</maj:origineNom>' %
                   origine_nom_trans.translate_out(_get(usager, 'origine_nom')))
        prenoms = format_name(' '.join(_get(usager, 'prenoms', ())), max=32)
        xml.append(
            '<maj:prenomRessortissantEtranger>%s</maj:prenomRessortissantEtranger>' % prenoms)
        xml.append('<maj:sexe>%s</maj:sexe>' % usager['sexe'])
        if _get(usager, 'sexe') == 'F':
            nom_usage = format_name(_get(usager, 'nom_usage', 'SNC'), max=41)
            if nom_usage not in ('INC', 'SNC'):
                xml.append('<maj:origineNomUsage>%s</maj:origineNomUsage>' %
                           origine_nom_trans.translate_out(_get(usager, 'origine_nom_usage')))
        else:
            nom_usage = ''
        xml.append('<maj:nomUsage>%s</maj:nomUsage>' % nom_usage)
        xml.append('<maj:dateDeNaissance>%s</maj:dateDeNaissance>' %
                   format_date(_get(usager, 'date_naissance')))
        xml.append('<maj:paysDeNaissance>%s</maj:paysDeNaissance>' %
                   pays_trans.translate_out(_get(_get(usager, 'pays_naissance', {}), 'code')))
        xml.append('<maj:villeDeNaissance>%s</maj:villeDeNaissance>' %
                   format_text(_get(usager, 'ville_naissance'),
                               max=28, allowed_pattern=r"[A-Za-z '\.\-,]"))
        xml.append('<maj:situationMatrimoniale>%s</maj:situationMatrimoniale>' %
                   sit_fam_trans.translate_out(_get(usager, 'situation_familiale')))
        nationalites = _get(usager, 'nationalites')
        if nationalites:
            xml.append('<maj:nationalite>%s</maj:nationalite>' %
                       nationalite_trans.translate_out(nationalites[0]['code']))
        else:
            xml.append('<maj:nationalite/>')
        xml.append('<maj:nomPere>%s</maj:nomPere>' %
                   format_name(_get(usager, 'nom_pere', 'INC'), max=21))
        xml.append('<maj:prenomPere>%s</maj:prenomPere>' %
                   format_name(_get(usager, 'prenom_pere', 'INC'), max=10))
        xml.append('<maj:nomMere>%s</maj:nomMere>' %
                   format_name(_get(usager, 'nom_mere', 'INC'), max=21))
        xml.append('<maj:prenomMere>%s</maj:prenomMere>' %
                   format_name(_get(usager, 'prenom_mere', 'INC'), max=10))
        adresse = _get_adresse(usager)
        if adresse:
            xml += format_address(adresse)
        return xml

    @staticmethod
    def _build_da(da, usager):
        if not da:
            date_entree_en_france = format_date(_get(usager, 'date_entree_en_france'))
            return ['<maj:dateEntreeEnFrance>%s</maj:dateEntreeEnFrance>' % date_entree_en_france,
                    '<maj:dateDepotDemande/>',
                    '<maj:typeProcedure/>',
                    '<maj:motifQualification/>',
                    '<maj:dateQualification/>',
                    '<maj:dateNotificationQualification/>',
                    '<maj:conditionEntreeEnFrance/>',
                    '<maj:indicateurVisa/>',
                    '<maj:decisionSurAttestation/>',
                    '<maj:dateDecisionAttestation/>',
                    '<maj:motifRefus/>',
                    '<maj:dateNotificationRefus/>']

        xml = []
        # if 'identifiants_eurodac' in usager:
        #     id_eurodac = _get(usager, 'identifiants_eurodac')[-1]
        #     xml.append('<maj:NumeroEurodac>%s</maj:NumeroEurodac>' % id_eurodac)
        xml.append('<maj:dateEntreeEnFrance>%s</maj:dateEntreeEnFrance>' %
                   format_date(da.get('date_entree_en_france')))

        xml.append('<maj:dateDepotDemande>%s</maj:dateDepotDemande>' %
                   format_date(da['date_demande']))
        procedure = da['procedure']
        procedure_type = proc_trans.translate_out(procedure['type'])
        xml.append('<maj:typeProcedure>%s</maj:typeProcedure>' % procedure_type)
        xml.append('<maj:motifQualification>%s</maj:motifQualification>' %
                   format_text(procedure.get('motif_qualification', 'NA'), max=5))
        xml.append('<maj:dateQualification>%s</maj:dateQualification>' %
                   format_date(da.get('date_enregistrement')))
        # TODO
        # xml.append('<maj:dateNotificationQualification>%s</maj:dateNotificationQualification>'
        # % '')
        cond_en_fr = cond_entree_france_trans.translate_out(da['condition_entree_france'])
        xml.append('<maj:conditionEntreeEnFrance>%s</maj:conditionEntreeEnFrance>' % cond_en_fr)
        xml.append('<maj:indicateurVisa>%s</maj:indicateurVisa>' %
                   format_bool(da.get('indicateur_visa_long_sejour')))
        xml.append('<maj:decisionSurAttestation>%s</maj:decisionSurAttestation>' %
                   format_bool(da.get('decision_sur_attestation')))
        if da.get('date_decision_sur_attestation'):
            xml.append('<maj:dateDecisionAttestation>%s</maj:dateDecisionAttestation>' %
                       format_date(da.get('date_decision_sur_attestation')))
        if da.get('motif_refus'):
            xml.append('<maj:motifRefus>%s</maj:motifRefus>' %
                       format_text(da.get('motif_refus'), max=4))
            # TODO
            xml.append('<maj:dateNotificationRefus>%s</maj:dateNotificationRefus>' % '')
        xml += format_demande(da)
        xml += format_date_decision(usager)
        return xml
