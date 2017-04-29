import json
import csv
import random
import unicodedata
import base64
from datetime import datetime, timedelta
from faker import Factory

from flask import current_app
from flask.ext.script import Manager, prompt, prompt_pass

from sief.model.utilisateur import Utilisateur
from sief.model.usager import Usager
from sief.model.recueil_da import RecueilDA
from sief.model.eurodac import generate_eurodac_ids
from sief.model.demande_asile import DecisionDefinitive
from sief.model.site import Prefecture, GU, StructureAccueil, Creneau
from sief.model.fichier import Fichier

populate_manager = Manager(usage="Auto populate database")

# JSON
JSON_PATH = 'sief/managers/populate/'


def _read_json(filename):
    with open(JSON_PATH + filename) as data_file:
        data = json.load(data_file)
        return data


# CSV
CSV_PATH = 'misc/'


def _init_csv():
    """Init a result csv file from Sites and Utilisateurs objects"""
    print(' *** Creating CSV files ***')
    with open('populate_sites.csv', 'w') as csvfile:
        writer = csv.writer(csvfile, delimiter=',', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(['type', 'libelle'])
    print('Created populate_sites.csv')

    with open('populate_utilisateurs.csv', 'w') as csvfile:
        writer = csv.writer(csvfile, delimiter=',', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(['role', 'email', 'nom', 'prenom', 'site_affecte', 'site_rattache'])
    print('Created populate_utilisateurs.csv')


def _write_site_csv(sites_dict):
    """Create a result csv file from Sites objects"""
    with open('populate_sites.csv', 'a') as csvfile:
        writer = csv.writer(csvfile, delimiter=',', quoting=csv.QUOTE_MINIMAL)
        for site_list in sites_dict:
            for site in sites_dict[site_list]:
                writer.writerow([site_list, site.libelle])


def _write_utilisateurs_csv(utilisateurs_list):
    """Create a result csv file from Utilisateurs objects"""
    with open('populate_utilisateurs.csv', 'a') as csvfile:
        writer = csv.writer(csvfile, delimiter=',', quoting=csv.QUOTE_MINIMAL)
        for utilisateur in utilisateurs_list:
            utilisateur_site_affecte = utilisateur.controller.get_current_site_affecte()
            utilisateur_site_rattache = utilisateur.controller.get_current_site_rattache()

            utilisateur_site_affecte = utilisateur_site_affecte.libelle \
                if utilisateur_site_affecte else None
            utilisateur_site_rattache = utilisateur_site_rattache.libelle \
                if utilisateur_site_rattache else None

            writer.writerow([utilisateur.controller.get_current_role(), utilisateur.email,
                             utilisateur.nom, utilisateur.prenom,
                             utilisateur_site_affecte, utilisateur_site_rattache])


def _read_csv(filename):
    with open(CSV_PATH + filename, encoding='utf-8') as data_file:
        data = list(csv.DictReader(data_file, delimiter=";"))
        return data


langues_iso = _read_csv("referentiel_langues_iso639-2.csv")
langues_ofpra = _read_csv("referentiel_langues_OFPRA.csv")
nationalites = _read_csv("referentiel_nationalites.csv")
pays = _read_csv("referentiel_pays_iso3166-1.csv")
origine_nom = ["EUROPE", "ARABE", "CHINOISE", "TURQUE/AFRIQ"]
situation_familiale = ["CELIBATAIRE", "DIVORCE", "MARIE", "CONCUBIN",
                       "SEPARE", "VEUF", "PACSE"]

# Img
IMG_PATH = 'sief/managers/populate/'


def _read_img(filename):
    with open(IMG_PATH + filename, "rb") as data_file:
        data = base64.b64encode(data_file.read())
        return data


tempalte_img = _read_img("template.png")


# Generate unique identifier
def _unique_id(text_id):
    fake = Factory.create()
    ids = set()
    while True:
        new_id = fake.numerify(text=text_id)
        if new_id not in ids:
            ids.add(new_id)
            yield new_id


inerec_id = _unique_id("#########")
agdref_id = _unique_id("##########")
dna_id = _unique_id("######")
famille_dna_id = _unique_id("######")


# Progress bar decorator
def progress_bar(obj_name):
    def _progress_bar_decorator(func):

        def wrapper(*args, **kwargs):
            # Init progress bar
            print('%s ' % obj_name, flush=True, end='')

            nb_elts, ret = func(*args, **kwargs)

            # End progress bar
            print(' (%s elements) Done !' % nb_elts)
            return ret

        return wrapper

    return _progress_bar_decorator


# Sites
@progress_bar('Site')
def _create_sites(infos):
    """Create sites"""
    fake = Factory.create("fr_FR")

    # all sites created
    created = {
        'prefectures': [],
        'gus': [],
        'accueils': []
    }
    nb_prefectures = random.randint(1, infos["nb_max_prefectures"])
    nb_gus = random.randint(1, infos["nb_max_gus"])
    nb_accueils = random.randint(1, infos["nb_max_accueils"])
    nb_sites = nb_prefectures + nb_gus + nb_accueils

    def _add_creneaux(site):
        today = datetime.utcnow().replace(hour=8, minute=0, second=0, microsecond=0)
        # x Days
        for i in range(infos["creneaux"]["nb_days"]):
            start = today + timedelta(days=i + 1)
            # y Créneaux by day
            for _ in range(infos["creneaux"]["nb_creneaux"]):
                end = start + timedelta(0, 45 * 60)
                # z Agents
                for _ in range(infos["creneaux"]["nb_agents"]):
                    cr = Creneau(date_debut=start, date_fin=end, site=site)
                    cr.save()
                start = end

    def _save(site):
        while True:
            try:
                site.save()
                # Progress bar
                print('.', flush=True, end='')
                break
            except Exception:
                site.libelle = fake.company() + '-' + fake.numerify(text="####")

        return site

    def _fake_payload():
        payload = {}
        payload["libelle"] = fake.company()
        payload["adresse"] = {
            'numero_voie': fake.building_number(),
            'voie': fake.street_address(),
            'code_insee': fake.numerify(text="#####"),
            'code_postal': fake.numerify(text="#####"),
            'ville': fake.city(),
            'longlat': [fake.longitude(), fake.latitude()]
        }
        return payload

    # Create Prefectures
    for _ in range(nb_prefectures):
        payload = _fake_payload()
        payload["code_departement"] = fake.numerify(text="###")
        prefecture = Prefecture(**payload)
        created["prefectures"].append(_save(prefecture))

    # Create GUs
    for _ in range(nb_gus):
        payload = _fake_payload()
        payload["autorite_rattachement"] = random.choice(created["prefectures"])
        gu = _save(GU(**payload))
        _add_creneaux(gu)
        created["gus"].append(gu)

    # Create Accueils
    for _ in range(nb_accueils):
        payload = _fake_payload()
        payload["guichets_uniques"] = random.sample(created["gus"],
                                                    random.randint(1, nb_gus))
        accueil = StructureAccueil(**payload)
        created["accueils"].append(_save(accueil))

    return nb_sites, created


# Users
@progress_bar('Utilisateur')
def _create_users(infos, password, sites):
    """Create users"""
    fake = Factory.create("fr_FR")
    created = []

    def _remove_accents(data):
        return unicodedata.normalize('NFKD', data.replace(' ', '')) \
            .encode('ASCII', 'ignore').lower()

    def _save(user):
        while True:
            try:
                user.save()
                # Progress bar
                print('.', flush=True, end='')
                break
            except Exception:
                user.email = user.email.replace("@test.com",
                                                fake.numerify(text="#") + '@test.com')
        return user

    def _fake_payload():
        payload = {
            'nom': fake.last_name().capitalize(),
            'prenom': fake.first_name().capitalize(),
        }
        payload["email"] = _remove_accents(payload["prenom"] + '.' +
                                           payload["nom"] + '@test.com')
        return payload

    def _create_loop(creator):
        for utilisateur in infos[creator]["createUtilisateur"]:
            for _ in range(random.randint(1, infos[utilisateur]["nb_max"])):
                payload = _fake_payload()
                payload_accreditation = {}
                payload_accreditation["role"] = infos[utilisateur]["role"]

                if "site" in infos[utilisateur]:
                    site_type = infos[utilisateur]["site"]
                    payload_accreditation["site_affecte"] = random.choice(sites[site_type])
                elif "site" in infos[creator]:
                    site_type = infos[creator]["site"]
                    payload_accreditation["site_affecte"] = random.choice(sites[site_type])

                if "site_affecte" in payload_accreditation:
                    if hasattr(payload_accreditation["site_affecte"], "autorite_rattachement"):
                        payload_accreditation["site_rattache"] = payload_accreditation[
                            "site_affecte"].autorite_rattachement

                    else:
                        payload_accreditation[
                            "site_rattache"] = payload_accreditation["site_affecte"]

                new = Utilisateur(**payload)
                new.controller.add_accreditation(**payload_accreditation)
                new.controller.init_basic_auth()
                new.controller.set_password(password)
                created.append(_save(new))

                if "createUtilisateur" in infos[utilisateur]:
                    _create_loop(utilisateur)

    _create_loop('admin')

    return len(created), created


# Usagers with auth
@progress_bar('Usager with auth')
def _create_usager_with_auth(infos, password):
    fake = Factory.create("fr_FR")
    created = []

    def _remove_accents(data):
        return unicodedata.normalize('NFKD', data.replace(' ', '')) \
            .encode('ASCII', 'ignore').lower()

    def _save(user):
        while True:
            try:
                user.save()
                # Progress bar
                print('.', flush=True, end='')
                break
            except Exception:
                user.email = user.email.replace("@test.com",
                                                fake.numerify(text="#") + '@test.com')
        return user

    def _fake_payload():
        payload = {
            'nom': fake.last_name().capitalize(),
            'nom_usage': fake.last_name().capitalize(),
            'prenoms': [fake.first_name().capitalize()],
            'sexe': random.choice(["M", "F"]),
            'date_naissance': fake.date_time_between_dates(
                datetime_start=datetime.utcnow() - timedelta(days=100 * 365),
                datetime_end=datetime.utcnow() - timedelta(days=3)),
            'pays_naissance': random.choice(pays),
            'ville_naissance': fake.city(),
            'nationalites': [random.choice(nationalites)],
            'situation_familiale': random.choice(situation_familiale),
            'numero_passeport': fake.numerify(text="##########"),
            'identifiant_agdref': fake.numerify(text="##########")
        }
        payload["email"] = _remove_accents(payload["prenoms"][0] + '.' +
                                           payload["nom"] + '@test.com')
        return payload

    def _create_loop(creator):
        for _ in range(random.randint(1, infos[creator]["nb_max"])):
            payload = _fake_payload()
            new = Usager(**payload)
            new.controller.init_basic_auth()
            new.controller.set_password(password)
            created.append(_save(new))

    _create_loop('no_profil')

    return len(created), len(created)


# Recueils
@progress_bar('Recueil')
def _create_recueils(infos, users, fake_id):
    """Create Recueils and Demandes Asile"""
    fake = Factory.create()
    all_created = {
        "recueils": [],
        "usagers": []
    }

    def _is_minor(birthday):
        # See sief/model/usager.py: function is_adult(usager)
        today = datetime.now()
        age = today.year - birthday.year
        if (today.month < birthday.month or
                (today.month == birthday.month and today.day < birthday.day)):
            age -= 1
        return age < 18

    def _fake_user(demandeur, datetime_start=None):
        payload = {
            'demandeur': demandeur,
            'nom': fake.last_name().capitalize(),
            'sexe': random.choice(["M", "F"]),
            'nationalites': [random.choice(nationalites)],
            'ville_naissance': fake.city(),
            'pays_naissance': random.choice(pays),
            'situation_familiale': random.choice(situation_familiale),
            "adresse": {"adresse_inconnue": True},
            'telephone': '0123456789',
            'vulnerabilite': {'mobilite_reduite': False}
        }

        if datetime_start:
            payload["date_naissance"] = fake.date_time_between_dates(
                datetime_start=datetime_start,
                datetime_end=datetime.utcnow() - timedelta(days=3))
        else:
            payload["date_naissance"] = fake.date_time_between_dates(
                datetime_start=datetime.utcnow() - timedelta(days=100 * 365),
                datetime_end=datetime.utcnow() - timedelta(days=3))

        if payload["sexe"] is "M":
            payload["prenoms"] = [fake.first_name_male().capitalize()]
        else:
            payload["prenoms"] = [fake.first_name_female().capitalize()]

        if payload["demandeur"] is True:
            payload["present_au_moment_de_la_demande"] = True
            payload["origine_nom"] = random.choice(origine_nom)
            payload["photo_premier_accueil"] = photo
            payload["date_depart"] = fake.date_time_between_dates(
                datetime_start=payload["date_naissance"],
                datetime_end=datetime.utcnow() - timedelta(days=2))
            payload["date_depart_approximative"] = random.choice([True, False])
            payload["date_entree_en_france"] = fake.date_time_between_dates(
                datetime_start=payload["date_depart"],
                datetime_end=datetime.utcnow() - timedelta(days=1))
            payload["date_entree_en_france_approximative"] = random.choice([True, False])
            payload["langues"] = [random.choice(langues_iso)]
            payload["langues_audition_OFPRA"] = [random.choice(langues_ofpra)]
        else:
            payload["present_au_moment_de_la_demande"] = random.choice([True, False])

        return payload

    def _fake_payload():
        payload = {}
        # usager_1
        payload["usager_1"] = _fake_user(True)
        # usager_2
        if payload["usager_1"]["situation_familiale"] in ["MARIE", "CONCUBIN", "PACSE"]:
            payload["usager_2"] = _fake_user(random.choice([True, False]),
                                             payload["usager_1"]["date_naissance"])
            del payload["usager_2"]["situation_familiale"]
        # enfants
        payload["enfants"] = []

        # usager_1 is minor or without children
        if (_is_minor(payload["usager_1"]["date_naissance"]) or
                random.randint(0, 100) >= infos["stats"]["percent_with_children"]):
            return payload

        for _ in range(random.randint(1, 3)):
            enfant = _fake_user(random.choice([True, False]),
                                payload["usager_1"]["date_naissance"])
            enfant["usager_1"] = random.choice([True, False])
            if "usager_2" in payload:
                enfant["usager_2"] = random.choice([True, False])
            else:
                enfant["usager_2"] = False
            payload["enfants"].append(enfant)

        return payload

    def _profil_demande(payload):
        if _is_minor(payload["usager_1"]["date_naissance"]):
            return 'MINEUR_ISOLE'

        for enfant in payload["enfants"]:
            if enfant["demandeur"]:
                if _is_minor(enfant["date_naissance"]):
                    return 'MINEUR_ACCOMPAGNANT'

        has_usager_2 = ("usager_2" in payload and
                        (payload["usager_2"]["demandeur"] or
                         payload["usager_2"]["present_au_moment_de_la_demande"]))
        has_children = len(payload["enfants"]) > 0

        if has_usager_2 or has_children:
            return "FAMILLE"

        return "ADULTE_ISOLE"

    def _update_to_id(user, usager_1):
        user.photo = user.photo_premier_accueil

        # Fake identifiant_agdref and date_enregistrement_agdref
        if fake_id:
            user.identifiant_agdref = next(agdref_id)
            user.date_enregistrement_agdref = datetime.utcnow()

        if _is_minor(user.date_naissance):
            user.representant_legal_nom = usager_1.nom
            user.representant_legal_prenom = usager_1.prenoms[0]

        user.identifiant_eurodac = generate_eurodac_ids()[0]

        return user

    def _update_to_exp(user):
        user.date_decision_sur_attestation = datetime.now()
        user.decision_sur_attestation = True

        if fake_id:
            user.identifiant_dna = next(dna_id)
            user.date_dna = datetime.now()

        procedure = random.choice(infos["procedures"])
        user.type_procedure = procedure["type"]
        user.motif_qualification_procedure = random.choice(procedure["motif"])

        user.visa = random.choice(infos["visa"])
        if user.visa == "D":
            user.indicateur_visa_long_sejour = True
        else:
            user.indicateur_visa_long_sejour = False
        user.condition_entree_france = random.choice(infos["conditions"])
        user.conditions_exceptionnelles_accueil = random.choice([True, False])
        if user.conditions_exceptionnelles_accueil:
            user.motif_conditions_exceptionnelles_accueil = \
                random.choice(infos["motif_cond_except"])

        return user

    def _edit_attestation(user, usagers):
        das = []

        date_debut_validite = datetime.now()
        date_fin_validite = date_debut_validite + timedelta(days=500)
        date_decision_sur_attestation = date_debut_validite

        da = usagers["usager_1"]["demande_asile"]
        da.controller.editer_attestation(
            user=user,
            date_debut_validite=date_debut_validite,
            date_fin_validite=date_fin_validite,
            date_decision_sur_attestation=date_decision_sur_attestation)
        da.save()
        das.append(da)

        if usagers["usager_2"] and "demande_asile" in usagers["usager_2"]:
            da = usagers["usager_2"]["demande_asile"]
            da.controller.editer_attestation(
                user=user,
                date_debut_validite=date_debut_validite,
                date_fin_validite=date_fin_validite,
                date_decision_sur_attestation=date_decision_sur_attestation)
            da.save()
            das.append(da)

        for enfant in usagers["enfants"]:
            if "demande_asile" in enfant:
                da = enfant["demande_asile"]
                da.controller.editer_attestation(
                    user=user,
                    date_debut_validite=date_debut_validite,
                    date_fin_validite=date_fin_validite,
                    date_decision_sur_attestation=date_decision_sur_attestation)
                da.save()
                das.append(da)

        return das

    photo = Fichier(name='template.png')
    photo.data.put(base64.decodestring(tempalte_img), content_type='image/png')
    photo.controller.save_or_abort()

    for user in users:
        created = {
            "brouillon": [],
            "pa_realise": [],
            "demandeur_ident": [],
            "exploite": [],
            "annule": [],
            "usagers": [],
            "das": [],
            "intro_ofpra": [],
            "decision_def": [],
            "fin_proc": []
        }

        for _ in range(random.randint(1, infos["stats"]["nb_max_by_creator"])):
            payload = _fake_payload()

            if user.controller.get_current_role() in ["RESPONSABLE_PA", "GESTIONNAIRE_PA"]:
                recueil = RecueilDA(statut="BROUILLON",
                                    profil_demande=_profil_demande(payload),
                                    structure_accueil=user.controller.get_current_site_affecte(),
                                    agent_accueil=user, **payload)
                recueil.save()
                created["brouillon"].append(recueil)

            else:
                recueil = RecueilDA(statut="PA_REALISE",
                                    profil_demande=_profil_demande(payload),
                                    date_transmission=datetime.utcnow(),
                                    structure_accueil=user.controller.get_current_site_affecte(),
                                    structure_guichet_unique=user.controller.get_current_site_affecte(),
                                    prefecture_rattachee=user.controller.get_current_site_affecte().autorite_rattachement,
                                    agent_accueil=user, **payload)
                if fake_id:
                    recueil.identifiant_famille_dna = next(famille_dna_id)
                recueil.save()
                created["pa_realise"].append(recueil)

            # Get all recueils in all_created
            print('.', flush=True, end='')
            all_created["recueils"].append(recueil)

        # Brouillon To PA Realise
        for brouillon in created["brouillon"]:
            if random.randint(0, 100) < infos["stats"]["percent_b_to_pa"]:
                if fake_id:
                    recueil.identifiant_famille_dna = next(famille_dna_id)
                brouillon.controller.pa_realiser()
                brouillon.save()
                created["pa_realise"].append(brouillon)

        # PA Realise to Demandeurs Identifies
        for pa_realise in created["pa_realise"]:
            if random.randint(0, 100) < infos["stats"]["percent_pa_to_id"]:
                usr = pa_realise.usager_1
                pa_realise.usager_1 = _update_to_id(pa_realise.usager_1, usr)
                pa_realise.usager_1['identite_approchante_select'] = True
                if pa_realise.usager_2:
                    pa_realise.usager_2['identite_approchante_select'] = True
                    if pa_realise.usager_2.demandeur:
                        pa_realise.usager_2 = _update_to_id(pa_realise.usager_2, usr)
                for enfant in pa_realise.enfants:
                    enfant['identite_approchante_select'] = True
                    if enfant.demandeur:
                        enfant = _update_to_id(enfant, usr)

                pa_realise.controller.identifier_demandeurs()
                pa_realise.save()
                created["demandeur_ident"].append(pa_realise)
            elif user.controller.get_current_role() in ["RESPONSABLE_GU_ASILE_PREFECTURE",
                                                        "GESTIONNAIRE_GU_ASILE_PREFECTURE"] and \
                    random.randint(0, 100) < infos["stats"]["percent_annule"]:
                pa_realise.controller.annuler(user,
                                              random.choice(infos["motifs_annulation"]))
                pa_realise.save()
                created["annule"].append(pa_realise)

        # Demandeurs Identifies To Exploite
        for dem_ident in created["demandeur_ident"]:
            if random.randint(0, 100) < infos["stats"]["percent_id_to_exploite"]:
                dem_ident.usager_1 = _update_to_exp(dem_ident.usager_1)
                if dem_ident.usager_2 and dem_ident.usager_2.demandeur:
                    dem_ident.usager_2 = _update_to_exp(dem_ident.usager_2)
                for enfant in dem_ident.enfants:
                    if enfant.demandeur:
                        enfant = _update_to_exp(enfant)
                usagers = dem_ident.controller.exploiter(user)
                dem_ident.save()
                created["exploite"].append(dem_ident)
                created["usagers"].append(usagers)

        # Edition Attestation
        if user.controller.get_current_role() in ["RESPONSABLE_GU_ASILE_PREFECTURE",
                                                  "GESTIONNAIRE_GU_ASILE_PREFECTURE"]:
            for usagers in created["usagers"]:
                if random.randint(0, 100) < infos["stats"]["percent_edit_attestation"]:
                    created["das"] += _edit_attestation(user, usagers)

        # Intro OFPRA
        if fake_id:
            for da in created["das"]:
                if (da.statut == "EN_ATTENTE_INTRODUCTION_OFPRA" and
                        random.randint(0, 100) < infos["stats"]["percent_intro_ofpra"]):
                    da.controller.introduire_ofpra(
                        identifiant_inerec=next(inerec_id),
                        date_introduction_ofpra=datetime.utcnow())
                    da.save()
                    created["intro_ofpra"].append(da)
                elif (da.statut == "EN_COURS_PROCEDURE_DUBLIN" and
                        random.randint(0, 100) < infos["stats"]["percent_fin_proc"]):
                    da.controller.finir_procedure()
                    da.save()
                    created["fin_proc"].append(da)

            # Decision Def
            for ofpra in created["intro_ofpra"]:
                if random.randint(0, 100) < infos["stats"]["percent_decision_def"]:
                    entite = random.choice(infos["entites"])
                    numero_skipper = None
                    if entite["entite"] == "CNDA":
                        numero_skipper = fake.numerify(text="########")
                    ofpra.decisions_definitives = [DecisionDefinitive(
                        nature=random.choice(entite["nature"]),
                        date=datetime.utcnow(),
                        date_premier_accord=datetime.utcnow(),
                        date_notification=datetime.utcnow(),
                        entite=entite["entite"],
                        numero_skipper=numero_skipper)]
                    ofpra.controller.passer_decision_definitive()
                    ofpra.save()
                    created["decision_def"].append(ofpra)

            for decision_def in created["decision_def"]:
                if random.randint(0, 100) < infos["stats"]["percent_fin_proc"]:
                    decision_def.controller.finir_procedure()
                    decision_def.save()
                    created["fin_proc"].append(decision_def)

        # Get all usagers in all_created
        for usagers in created["usagers"]:
            all_created["usagers"].append(usagers["usager_1"]["usager"])
            if "usager" in usagers["usager_2"]:
                all_created["usagers"].append(usagers["usager_2"]["usager"])
            for enfant in usagers["enfants"]:
                all_created["usagers"].append(enfant["usager"])

    return len(all_created["recueils"]), len(all_created["usagers"])


@populate_manager.option('-p', '--password', help="Password of all users")
@populate_manager.option('-u', '--usagers', help="The minimum number of usagers")
@populate_manager.option('-f', '--fake',
                         help="Create fake identifiers (DN@, Famille DN@, INEREC and AGDREF)",
                         action='store_true')
@populate_manager.option('-l', '--log',
                         help="Write informations into CSV files", action='store_true')
def database(password=None, usagers=None, fake=False, log=False):
    """Create our database"""

    if not current_app.config['POPULATE_DB']:
        print(' *** Creating DataBase ***')
        print('[ABORTED]\nDefine an environment variable POPULATE_DB=true to use this script')
        return

    # Get password and the minimum number of usagers
    while not password:
        password = prompt_pass('users password')
        pass_confirm = prompt_pass('confirm password')
        if password != pass_confirm:
            print('Password mismatched')
            password = None
        else:
            break
    usagers = usagers or prompt('How many usagers do you want')

    # Init CSV files
    if log:
        _init_csv()

    # Read Json file
    infos = _read_json('infos.json')

    # Create sites, users, recueil, da and usagers
    print(' *** Creating DataBase ***')
    nb_usagers_min = int(usagers)
    nb_usagers = 0
    while nb_usagers < nb_usagers_min:
        progress = (nb_usagers * 10) // nb_usagers_min
        print('\nDataBase progress: [{0}] {1}%'.format('#' * progress + '-' * (10 - progress),
                                                       str(progress * 10)))
        sites = _create_sites(infos["sites"])
        users = _create_users(infos["utilisateurs"], password, sites)
        creators_role = infos["recueils"]["creators"]
        creators_user = [user for user in users if user.controller.get_current_role()
                         in creators_role]

        nb_created_usagers = _create_recueils(infos["recueils"], creators_user, fake_id=fake)
        nb_created_usagers_with_auth = _create_usager_with_auth(infos["usagers_with_auth"],
                                                                password)
        nb_usagers += nb_created_usagers + nb_created_usagers_with_auth

        print('Usager (%s elements) Done !' % nb_usagers)
        if log:
            _write_site_csv(sites)
            _write_utilisateurs_csv(users)

    print('\nDataBase progress: [{0}] 100%  Done !'.format('#' * 10))

if __name__ == "__main__":
    populate_manager.run()
