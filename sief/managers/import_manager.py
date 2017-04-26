from flask.ext.script import Manager
from csv import reader, QUOTE_NONE
from sief.model.site import Site
from sief.model.utilisateur import Utilisateur


import_manager = Manager(usage="Perform import operations")


@import_manager.option('file', help="CSV file containing users to import")
@import_manager.option('-d', '--delimiter', help="delimiter for CSV fields (default: ',')",
                       default=',')
@import_manager.option('-f', '--force', action='store_true', default=False,
                       help="replace the element if it exists in database")
@import_manager.option('-r', '--remove', action='store_true', default=False,
                       help="remove the elements")
def user(file, delimiter, force, remove):
    from core.auth import encrypt_password, generate_password
    header = {}
    sites = {}  # used to reduce access to DB
    with open(file, 'r') as file:
        csv = reader(file, delimiter=delimiter, quoting=QUOTE_NONE)
        for entry in csv:
            entry = [x or None for x in entry]
            if not header:
                for id, col in enumerate(entry):
                    header[col] = id
                continue
            site = sites.get(entry[header['site_affecte']], False)
            if site is False:
                site = Site.objects(libelle=entry[header['site_affecte']]).first()
                sites[entry[header['site_affecte']]] = site
            if site is None and entry[header['role']] not in ('ADMINISTRATEUR_NATIONAL',
                                                              'RESPONSABLE_NATIONAL'):
                print('Utilisateur non valide : %s' % entry)

            site_rattache = None
            if site and entry[header['role']] in ('ADMINISTRATEUR_PA', 'RESPONSABLE_PA',
                                                  'GESTIONNAIRE_PA', 'ADMINISTRATEUR_PREFECTURE',
                                                  'GESTIONNAIRE_ASILE_PREFECTURE'):
                site_rattache = site

            if site and entry[header['role']] in ('RESPONSABLE_GU_ASILE_PREFECTURE',
                                                  'GESTIONNAIRE_GU_ASILE_PREFECTURE',
                                                  'RESPONSABLE_GU_DT_OFII',
                                                  'GESTIONNAIRE_GU_DT_OFII'):
                site_rattache = site.autorite_rattachement

            email = entry[header['email']]
            if force or remove:
                obj = Utilisateur.objects(email=email).first()
                if obj:
                    print('Overwriting %s (was %s)' % (email, obj.pk))
                    obj.delete()

            # Don't try to create if remove is setted
            if remove:
                continue
            try:
                password = generate_password()
                user = Utilisateur(email=email,
                                   nom=entry[header['nom']],
                                   prenom=entry[header['prenom']],
                                   telephone=entry[header['telephone']]).save()
                user.controller.add_accreditation(role=entry[header['role']],
                                                  site_affecte=site, site_rattache=site_rattache)
                user.controller.init_basic_auth()
                user.controller.email_password(password)
            except Exception as exc:
                print('Utilisateur non valide : %s : %s' % (entry, str(exc)))


@import_manager.option('file', help="CSV file containing users to import")
@import_manager.option('-d', '--delimiter', help="delimiter for CSV fields (default: ',')",
                       default=',')
@import_manager.option('-f', '--force', action='store_true', default=False,
                       help="replace the element if it exists in database")
@import_manager.option('-r', '--remove', action='store_true', default=False,
                       help="remove the elements")
def site(file, delimiter, force, remove):
    from sief.model.site import StructureAccueil, Prefecture, GU
    from sief.model.fields import AddressEmbeddedDocument
    header = {}
    prefs = {}
    gus = {}
    with open(file, 'r') as file:
        csv = reader(file, delimiter=delimiter, quoting=QUOTE_NONE)
        for entry in csv:
            entry = [x or None for x in entry]
            if not header:
                for id, col in enumerate(entry):
                    header[col] = id
                continue
            libelle = entry[header['libelle']]
            if force or remove:
                obj = Site.objects(libelle=libelle).first()
                if obj:
                    print('Overwriting %s (was %s)' % (libelle, obj.pk))
                    obj.delete()

            # Don't try to create if remove is setted
            if remove:
                continue
            # Check site type
            try:
                adresse = AddressEmbeddedDocument(
                    chez=entry[header['adresse.chez']],
                    complement=entry[header['adresse.complement']],
                    numero_voie=entry[header['adresse.numero_voie']],
                    voie=entry[header['adresse.voie']],
                    code_insee=entry[header['adresse.code_insee']],
                    code_postal=entry[header['adresse.code_postal']],
                    ville=entry[header['adresse.ville']])
                if entry[header['type']] == 'StructureAccueil':
                    # lookup GU
                    gu = gus.get('guichet_unique', False)
                    if gu is False:
                        gu = GU.objects(
                            libelle=entry[header['guichet_unique']]).first()
                        prefs[entry[header['guichet_unique']]] = gu
                    StructureAccueil(libelle=libelle,
                                     telephone=entry[header['telephone']],
                                     email=entry[header['email']],
                                     adresse=adresse,
                                     guichets_uniques=(gu.id,),
                                     ).save()

                elif entry[header['type']] == 'GU':
                    pref = prefs.get(entry[header['autorite_rattachement']], False)
                    if pref is False:
                        pref = Prefecture.objects(
                            libelle=entry[header['autorite_rattachement']]).first()
                        prefs[entry[header['autorite_rattachement']]] = pref
                    gu = GU(libelle=libelle,
                            telephone=entry[header['telephone']],
                            email=entry[header['email']],
                            adresse=adresse,
                            autorite_rattachement=pref,
                            limite_rdv_jrs=int(entry[header['limite_rdv_jrs']]))
                    gu.save()
                    gus[libelle] = gu

                elif entry[header['type']] == 'Prefecture':
                    pref = Prefecture(
                        libelle=libelle,
                        telephone=entry[header['telephone']],
                        email=entry[header['email']],
                        adresse=adresse,
                        code_departement=entry[header['code_departement']],
                        limite_rdv_jrs=int(entry[header['limite_rdv_jrs']]))
                    pref.save()
                    prefs[libelle] = pref

            except Exception as exc:
                print('Site non valide : %s : %s' % (entry, str(exc)))
