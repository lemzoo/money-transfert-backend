"""
Patch 1.0.5 => 1.0.6
Ajout du champ obligatoire code_departement aux prefectures
"""

from mongopatcher import Patch

PS = ""

patch_v106 = Patch('1.0.5', '1.0.6', patchnote=__doc__, ps=PS)


@patch_v106.fix
def add_field(db):
    col = db['site']

    for site in col.find({'_cls': 'Site.Prefecture'}):
        postcode = site.get('adresse', {}).get('code_postal')
        if postcode and len(postcode) >= 2:
            col.update({'_id': site['_id']}, {'$set': {'code_departement': postcode[:2] + '0'}})
        else:
            col.update({'_id': site['_id']}, {'$set': {'code_departement': '000'}})
