from flask.ext.script import Manager, prompt
from sief.model.demande_asile import DemandeAsile
from sief.model.usager import Usager
import csv
ofpra_manager = Manager(usage="Remove an Introduction OFPRA statut")


@ofpra_manager.option('-p', '--platform', help="Platform Identifier")
@ofpra_manager.option('-i', '--inerec', help="INEREC Identifier")
def remove(platform=None, inerec=None):
    """Remove an Introduction OFPRA"""
    da = None

    if inerec:
        da = DemandeAsile.objects.get_or_404(identifiant_inerec=inerec)
    else:
        identifier = platform or prompt(
            'Select a specific Demande Asile using this Platform Identifier')
        da = DemandeAsile.objects.get_or_404(id=identifier)

    if da.statut == "EN_COURS_INSTRUCTION_OFPRA":
        da.identifiant_inerec = None
        da.date_introduction_ofpra = None
        da.statut = "EN_ATTENTE_INTRODUCTION_OFPRA"
        da.save()
        print("DA (id: %s)" % da.id)
        print("Downgrade [success]")
    else:
        print("DA (id: %s)" % da.id)
        print("Downgrade [fail]: This status isn't 'EN_COURS_INSTRUCTION_OFPRA'")


@ofpra_manager.option('-f', '--file-name', dest='filename', default='export_ofpra.csv')
def export(filename):
    usagers = Usager.objects(telephone__exists=True)
    demande_asiles = DemandeAsile.objects(usager__in=usagers)
    with open(filename, 'w') as csvfile:
        writer = csv.writer(csvfile, delimiter=',')
        writer.writerow(['Id Inerec', 'Id Demande Asile', 'telephone'])
        for demande in demande_asiles:
            writer.writerow([demande.identifiant_inerec, demande.id, demande.usager.telephone])

if __name__ == "__main__":
    ofpra_manager.run()
