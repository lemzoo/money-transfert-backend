from dateutil.relativedelta import relativedelta
from connector.agdref.common import AGDREFProcessor, format_date, format_nombre_demande
from connector.agdref.translations import pays_trans


class DecisionDefinitiveOFPRACNDA(AGDREFProcessor):

    BASE_NAME = 'decisionDefinitiveOFPRACNDA'

    def _build_xml(self, msg):
        context = msg.context
        xml = self.headers(self.source, '15')

        da = context['demande_asile']
        decision = da.get('decisions_definitives', [])[0]
        usager = context['usager']
        xml.append(
            '<maj:numeroRessortissantEtranger>%s</maj:numeroRessortissantEtranger>' %
            usager['identifiant_agdref'])
        xml.append('<maj:identifiantSIAsile>%s</maj:identifiantSIAsile>' %
                   usager.get('identifiant_portail_agdref', ''))
        xml.append('<maj:numeroDemandeAsile>%s</maj:numeroDemandeAsile>' %
                   format_nombre_demande(usager))
        xml.append('<maj:dateNotification>%s</maj:dateNotification>' %
                   format_date(decision['date_notification']))
        entite = decision.get('entite') or ''
        xml.append('<maj:entite>%s</maj:entite>' % entite)
        skipper = decision.get('numero_skipper') or ''
        xml.append('<maj:numeroSKYPPER>%s</maj:numeroSKYPPER>' % skipper)
        xml.append('<maj:dateDecision>%s</maj:dateDecision>' % format_date(decision['date']))
        nature = decision['nature']
        if nature in ('DC', 'DE', 'RJ', 'DS', 'IAM', 'IF', 'ILE',
                      'IND', 'INR', 'IR', 'IRR', 'RJ', 'NOR', 'RJO', 'DS',
                                          'DSO', 'RDR', 'RIC', 'AI'):
            xml.append('<maj:decision>N</maj:decision>')
            if nature in ('DE', 'DS', 'DSO'):
                xml.append('<maj:desistement>O</maj:desistement>')
                xml.append('<maj:dateDesistement>%s</maj:dateDesistement>' %
                           format_date(decision['date']))
        else:
            xml.append('<maj:decision>O</maj:decision>')
            if nature in ('CR', 'TF', 'NL', 'NLO', 'AN', 'NLE', 'ANT'):
                xml.append('<maj:typeProtectionAccordee>REF</maj:typeProtectionAccordee>')
                xml.append('<maj:dateFinProtectionAccordee>%s</maj:dateFinProtectionAccordee>' %
                           format_date(decision['date'], delta=relativedelta(years=10)))
            elif nature in ('PS', 'PS1', 'PS2', 'ANP'):
                xml.append('<maj:typeProtectionAccordee>PSR</maj:typeProtectionAccordee>')
                xml.append('<maj:dateFinProtectionAccordee>%s</maj:dateFinProtectionAccordee>' %
                           format_date(decision['date'], delta=relativedelta(years=1)))
            pays_ex = decision.get('pays_exclus', [])
            for idx, pays in enumerate(pays_ex, 1):
                xml.append('<maj:paysExclu{0}>{1}</maj:paysExclu{0}>'.format(
                    idx, pays_trans.translate_out(pays.get('id', ''))))
        xml.extend(self.footer(self.source))
        return ''.join(xml)
