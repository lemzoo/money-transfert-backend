from functools import partial
from connector.agdref.common import AGDREFProcessor, format_text, format_date, format_bool, format_nombre_demande
from connector.agdref.translations import pays_trans, nationalite_trans


class ReconstitutionEtatCivilOFPRA(AGDREFProcessor):

    BASE_NAME = 'reconstitutionEtatCivilOFPRA'

    def _build_xml(self, msg):
        format_name = partial(format_text, allowed_pattern=r"[a-zA-Z \-']")
        usager = msg.context['usager']
        xml = self.headers(self.source, '16')
        # Code goes HERE
        xml.append('<maj:numeroRessortissantEtranger>%s</maj:numeroRessortissantEtranger>' %
                   usager.get('identifiant_agdref'))
        xml.append('<maj:identifiantSIAsile>%s</maj:identifiantSIAsile>' %
                   usager.get('identifiant_portail_agdref', ''))
        xml.append('<maj:numeroDemandeAsile>%s</maj:numeroDemandeAsile>' %
                   format_nombre_demande(usager))
        xml.append('<maj:etatCivilValide>%s</maj:etatCivilValide>' %
                   format_bool(usager.get('ecv_valide', '')))
        prenoms = format_name(' '.join(usager['prenoms']), max=32)
        xml.append('<maj:prenoms>%s</maj:prenoms>' % prenoms)
        nom = format_name(usager['nom'], max=44)
        xml.append('<maj:nomNaissance>%s</maj:nomNaissance>' % nom)
        nom_usage = format_name(usager.get('nom_usage'), max=41)
        xml.append('<maj:nomEpouse>%s</maj:nomEpouse>' % nom_usage)
        xml.append('<maj:dateNaissance>%s</maj:dateNaissance>' %
                   format_date(usager.get('date_naissance')))
        xml.append('<maj:paysNaissance>%s</maj:paysNaissance>' %
                   pays_trans.translate_out(usager.get('pays_naissance', {}).get('code')))
        xml.append('<maj:villeNaissance>%s</maj:villeNaissance>' %
                   format_text(usager.get('ville_naissance', ''), max=28,
                               allowed_pattern=r"[A-Za-z '.\-,]"))
        nationalites = usager.get('nationalites')
        nationalite = nationalite_trans.translate_out(
            nationalites[0]['code']) if nationalites else ''
        xml.append('<maj:nationalite>%s</maj:nationalite>' % nationalite)
        xml.append('<maj:sexe>%s</maj:sexe>' % usager['sexe'])
        xml.append('<maj:enfantDeRefugie>%s</maj:enfantDeRefugie>' %
                   format_bool(usager.get('enfant_de_refugie')))
        # END
        xml.extend(self.footer(self.source))

        return ''.join(xml)
