"""
Patch 1.1.2 => 1.1.3
Supprime les champs vides des adresses pour les code_insee et code_posal
"""

from mongopatcher import Patch

patch_v113 = Patch('1.1.2', '1.1.3', patchnote=__doc__)


@patch_v113.fix
def clean_usagers(db):
    usagers_col = db['usager']

    for usager in usagers_col.find({"$or": [
                {"localisations.adresse.code_insee": ""},
                {"localisations.adresse.code_postal": ""}
            ]}):
        localisations = usager['localisations']
        for localisation in localisations:
            adresse = localisation.get('adresse', {})
            for  field in ('code_insee', 'code_postal'):
                if adresse.get(field) is "":
                    del adresse[field]
        usagers_col.update({"_id": usager['_id']}, usager)


@patch_v113.fix
def clean_recueils(db):
    recueils_col = db['recueil_d_a']

    def _clean_usager(usager):
        adresse = usager.get('adresse', {})
        for  field in ('code_insee', 'code_postal'):
            if adresse.get(field) is "":
                del adresse[field]

    for recueil in recueils_col.find({"$or": [
                {"usager_1.adresse.code_insee": ""},
                {"usager_1.adresse.code_postal": ""},
                {"usager_2.adresse.code_insee": ""},
                {"usager_2.adresse.code_postal": ""},
                {"enfants.adresse.code_insee": ""},
                {"enfants.adresse.code_postal": ""}
            ]}):
        _clean_usager(recueil['usager_1'])
        if 'usager_2' in recueil:
            _clean_usager(recueil['usager_2'])
        for child in recueil.get('enfants', ()):
            _clean_usager(child)
        recueils_col.update({"_id": recueil['_id']}, recueil)
