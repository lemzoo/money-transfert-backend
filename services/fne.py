from requests import post
from requests.exceptions import RequestException
from xmltodict import parse
from datetime import datetime
from connector.tools import strip_namespaces, to_list
from connector.agdref.common import format_text, format_date
from connector.agdref.translations import pays_trans, nationalite_trans
from sief.model.referentials import CodeInseeAGDREF


class FNEBadRequestError(Exception):
    pass


class FNEConnectionError(Exception):
    pass


class FNEDisabledError(Exception):
    pass


class FNEBadDateError(Exception):
    pass


class FNETooManyResponse(Exception):
    pass


def _parse_date(value, isoformat=True):
    if value in (None, '', '00000000'):
        return None
    try:
        date = datetime.strptime(value, '%Y%m%d')
        if isoformat:
            return date.isoformat()
        else:
            return date
    except ValueError:
        raise FNEBadDateError()


class FNELookup:

    def __init__(self):
        self.disabled = False

    def init_app(self, app):
        app.config.setdefault('DISABLE_FNE', False)
        app.config.setdefault('FNE_TESTING_STUB', False)
        app.config.setdefault('FNE_URL', '')
        app.config.setdefault('FNE_HTTP_PROXY', '')
        app.config.setdefault('FNE_HTTPS_PROXY', '')
        self.disabled = app.config.get('DISABLE_FNE')
        self.url = app.config.get('FNE_URL')
        self.proxies = {
            'http': app.config.get('FNE_HTTP_PROXY'),
            'https': app.config.get('FNE_HTTPS_PROXY')
        }
        self.testing_stub = app.config.get('FNE_TESTING_STUB')
        if not self.testing_stub and not self.url:
            self.disabled = True

    def _build_xml(self, nom, prenom, date_naissance, sexe, nationalite,
                   commune_naissance, ts, identifiant_agdref=None):
        xml = []
        xml.append('<?xml version="1.0" encoding="UTF-8"?>'
                   '<soapenv:Envelope '
                   'xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"'
                   ' xmlns:asil="http://interieur.gouv.fr/asile/">')
        xml.append('<soapenv:Header/><soapenv:Body>')
        xml.append('<asil:consultationFNERequest>')
        xml.append('<asil:typeFlux>01</asil:typeFlux>')
        xml.append('<asil:dateEmissionFlux>%s</asil:dateEmissionFlux>' % ts.strftime("%Y%m%d"))
        xml.append('<asil:heureEmissionFlux>%s</asil:heureEmissionFlux>' %
                   ts.strftime("%H%M%S"))

        if identifiant_agdref:
            xml.append(
                '<asil:numeroRessortissantEtranger>%s</asil:numeroRessortissantEtranger>' % identifiant_agdref)
        else:
            xml.append('<asil:prenom>%s</asil:prenom>' % format_text(prenom))
            xml.append('<asil:nomPatronymique>%s</asil:nomPatronymique>' % format_text(nom))
            xml.append('<asil:sexe>%s</asil:sexe>' % format_text(sexe))
            if date_naissance not in (None, "null"):
                xml.append('<asil:dateNaissance>%s</asil:dateNaissance>' %
                           format_date(date_naissance))
            if commune_naissance:
                xml.append('<asil:communeNaissance>%s</asil:communeNaissance>' %
                           format_text(commune_naissance))
            if nationalite:
                xml.append('<asil:nationalite>%s</asil:nationalite>' %
                           format_text(nationalite_trans.translate_out(nationalite)))
        xml.append('</asil:consultationFNERequest>')
        xml.append('</soapenv:Body></soapenv:Envelope>')
        return ''.join(xml)

    def _get_code_insee(self, ville, code_postal=None):
        code_insee = "00000"
        if ville == "MARSEILLE" and code_postal:
            code_insee = str(int(code_postal) + 200)
        elif ville == "LYON" and code_postal:
            code_insee = str(int(code_postal) + 380)
        elif ville == "PARIS" and code_postal:
            code_insee = str(int(code_postal) + 100)
        else:
            ref_insee = CodeInseeAGDREF.objects(libelle=ville).first()
            if ref_insee:
                code_insee = ref_insee.code
        return code_insee

    def _parse(self, msg, xml):
        namespaces = {self.url: None}
        raw = parse(msg, process_namespaces=True, namespaces=namespaces)
        # Remove soap_enveloppe
        raw = raw.popitem()[1]
        raw = raw.popitem()[1]
        raw = raw.popitem()[1]
        raw = strip_namespaces(raw)
        if str(raw.get('codeRetour')) != '000':
            if str(raw.get('codeRetour')) == '206':
                raise FNETooManyResponse('Trop de réponses, veuillez affiner la recherche.')
            raise FNEBadRequestError("Server returned : %s Original request : %s" % (msg, xml))
        if raw.get('listeDossier'):
            results = []
            raw = raw['listeDossier'].get('Dossiers')
            raw = to_list(raw)
            for r in raw:
                if r.get('numeroEtranger'):
                    results.append(str(r.get('numeroEtranger')))
        elif raw.get('DossierComplet'):
            raw = raw['DossierComplet']
            results = {
                'identifiant_agdref': raw.get('numeroEtranger', ''),
                'identifiant_portail_agdref': raw.get('identifiantSIAsile', ''),

                'nom': raw.get('nom'),
                'nom_usage': raw.get('nomUsage'),
                'prenoms': (raw.get('prenom', ''),),
                'date_naissance': _parse_date(raw.get('dateNaissance')),
                'ville_naissance': raw.get('communeNaissance'),
                'pays_naissance': pays_trans.translate_in(raw.get('paysNaissance')),
                'nationalite': nationalite_trans.translate_in(raw.get('nationalite')),
                'sexe': raw.get('sexe'),
                'nom_pere': raw.get('nomPere'),
                'prenom_pere': raw.get('prenomPere'),
                'nom_mere': raw.get('nomMere'),
                'prenom_mere': raw.get('prenomMere'),
                'date_entree_en_france': _parse_date(raw.get('dateEntreeFrance')),
                'date_enregistrement_agdref': _parse_date(raw.get('dateEmissionFlux')),

                'localisations': {
                    'adresse': {
                        'numero_voie': raw.get('numeroVoie'),
                        'codeVoie': raw.get('codeVoie'),
                        'voie': raw.get('libelleVoie'),
                        'chez': raw.get('chez'),
                        'code_postal': raw.get('codePostal'),
                        'ville': raw.get('libelleCommune'),
                    },
                    'organisme_origine': 'AGDREF'
                },
                'numeroDossier': raw.get('numeroDossier'),
                'codeDepartement': raw.get('codeDepartement'),
                'codeSousPrefectureIPREF': raw.get('codeSousPrefectureIPREF'),
                'codeStatutJuridique': raw.get('codeStatutJuridique'),
                'typeTitreActuel': raw.get('typeTitreActuel'),
                'numeroDuplicata': raw.get('numeroDuplicata'),
                'dateDebutValiditeTitreActuel': _parse_date(raw.get('dateDebutValiditeTitreActuel')),
                'dateFinValiditeTitreActuel': _parse_date(raw.get('dateFinValiditeTitreActuel')),
                'referenceReglementaire': raw.get('referenceReglementaire'),
                'codeMouvement': raw.get('codeMouvement'),
                'indicateurArchivage': raw.get('indicateurArchivage'),
                'indicateurAlias': raw.get('indicateurAlias'),
                'numeroEtrangerReference': raw.get('numeroEtrangerReference'),
                'indicateurPresenceDemandeAsile': raw.get('indicateurPresenceDemandeAsile'),
                'typeTitreDemande': raw.get('typeTitreDemande'),
                'dateDebutValiditeTitreAttenteRemise': _parse_date(raw.get('dateDebutValiditeTitreAttenteRemise')),
                'dateFinValiditeTitreAttenteRemise': raw.get('dateFinValiditeTitreAttenteRemise'),
                'libelleGenreMesureAdministrative': raw.get('libelleGenreMesureAdministrative'),
                'libelleMesureAdministrative': raw.get('libelleMesureAdministrative')
            }
            if 'localisations' in results and 'adresse' in results["localisations"]:
                results["localisations"]["adresse"]["code_insee"] = self._get_code_insee(
                    results["localisations"]["adresse"].get('ville', ),
                    results["localisations"]["adresse"].get('code_postal', ))
        else:
            results = {}

        return results

    def _submit_query(self, xml):
        if xml is None:
            return 'Malformed query', None
        try:
            req = post(self.url, data=xml, proxies=self.proxies)
        except RequestException:
            raise FNEConnectionError('Erreur lors de la connexion avec AGDREF')
        return self._parse(req.text, xml)

    def query(self, nom=None, prenom=None, sexe=None, date_naissance=None, nationalite=None,
              commune_naissance=None, identifiant_agdref=None):
        if self.disabled:
            raise FNEDisabledError('Connecteur FNE desactive')
        if self.testing_stub:
            return {}
        if not identifiant_agdref:
            if not nom and not prenom and not sexe:
                return {}
        return self._submit_query(self._build_xml(nom=nom, prenom=prenom,
                                                  date_naissance=date_naissance,
                                                  sexe=sexe,
                                                  nationalite=nationalite,
                                                  commune_naissance=commune_naissance,
                                                  ts=datetime.utcnow(),
                                                  identifiant_agdref=identifiant_agdref))
fne_config = FNELookup()
lookup_fne = fne_config.query
