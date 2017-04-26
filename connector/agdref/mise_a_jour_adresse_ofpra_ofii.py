from connector.agdref.common import AGDREFProcessor, format_text, format_date, format_nombre_demande
from connector.agdref.translations import voie_trans, insee_to_libelle


def format_address(address):
    xml = []
    if not address:
        return xml
    for field_agdref, field_pf, max_size, allowed_pattern in (
            ('chez', 'chez', 21, r"[A-Za-z '.\-,]"),
            ('numeroVoie', 'numero_voie', 4, r"[A-Za-z0-9 ]"),
            ('codePostal', 'code_postal', 5, r"[0-9]"),
            ('codeINSEE', 'code_insee', 3, None)):
        value = address.get(field_pf)
        if value:
            xml.append('<maj:{field}>{value}</maj:{field}>'.format(
                field=field_agdref,
                value=format_text(value, max=max_size, allowed_pattern=allowed_pattern)))
    xml.append('<maj:libelleCommune>%s</maj:libelleCommune>' %
               insee_to_libelle(address)[:28])
    voie = format_text(address.get('voie'), allowed_pattern=r"[A-Za-z0-9 ,'\-]")
    if voie:
        xml.append('<maj:typeVoie>%s</maj:typeVoie>' %
                   voie_trans.translate_out(voie.split(' ', 1)[0])[:4])
        xml.append('<maj:libelleVoie>%s</maj:libelleVoie>' %
                   format_text(' '.join(voie.split(' ', 1)[1:])[:24]))
    return xml


class MiseAJourAdresse(AGDREFProcessor):

    BASE_NAME = 'miseAJourAdresse'

    def query(self, handler, msg):
        usager = msg.context['usager']
        if not usager.get('identifiant_agdref'):
            return "Seules les usagers avec un identifiant_agdref sont envoyés à AGDREF"
        origin = usager.get('localisation', {}).get('organisme_origine')
        if origin not in ('DNA', 'INEREC'):
            return "Seules les adressses venant de DNA et d'INEREC sont envoyées à AGDREF"
        return super().query(handler, msg)

    def _build_xml(self, msg):
        usager = msg.context['usager']
        if not usager.get('identifiant_agdref'):
            return
        origin = usager.get('localisation', {}).get('organisme_origine')
        if origin == 'DNA':
            self.BASE_NAME = 'miseAJourAdresseOFII'
            xml = self.headers(self.source, '18')
        elif origin == 'INEREC':
            self.BASE_NAME = 'miseAJourAdresseOFPRA'
            xml = self.headers(self.source, '19')
        xml.append(
            '<maj:numeroRessortissantEtranger>%s</maj:numeroRessortissantEtranger>' %
            usager.get('identifiant_agdref', ''))
        xml.append('<maj:identifiantSIAsile>%s</maj:identifiantSIAsile>' %
                   usager.get('identifiant_portail_agdref', ''))
        loc = usager['localisation']
        adresse = loc.get('adresse')
        xml.append('<maj:numeroDemandeAsile>%s</maj:numeroDemandeAsile>' %
                   format_nombre_demande(usager))
        xml += format_address(adresse)
        xml.append('<maj:organismeMAJ>%s</maj:organismeMAJ>' % loc.get('organisme_origine', ''))
        xml.append('<maj:dateMAJ>%s</maj:dateMAJ>' % format_date(loc['date_maj']))

        xml.extend(self.footer(self.source))
        return ''.join(xml)
