from datetime import timedelta

from django.utils import timezone

from core.models import Alerte
from monitoring.constants import ALERTES_MVP


class AlerteDeduplicationService:
    """Déduplique les alertes du moteur de surveillance (voir docs/sprints/sprint-05.md, Volet 3).

    monitoring n'écrit jamais dans finance/surveillance/vente — uniquement sur Alerte (core).
    """

    @staticmethod
    def get_ou_creer(type_alerte, defaults, **cles_identification):
        """Retourne (alerte, creee, doit_envoyer) pour la situation logique identifiée
        par (type_alerte, **cles_identification). Ne crée jamais de doublon ACTIVE."""
        existante = Alerte.objects.filter(
            type_alerte=type_alerte, statut="ACTIVE", **cles_identification
        ).first()

        if existante is None:
            alerte = Alerte.objects.create(
                type_alerte=type_alerte,
                statut="ACTIVE",
                date_dernier_envoi=timezone.now(),
                nombre_envois=1,
                **cles_identification,
                **defaults,
            )
            return alerte, True, True

        # Rafraîchit le contenu (message, niveau, produit...) même si on ne renvoie
        # pas de notification — une alerte ACTIVE sans reenvoi_heures ne doit pas
        # afficher indéfiniment les données du jour de sa création.
        champs_modifies = [
            champ for champ, valeur in defaults.items() if getattr(existante, champ) != valeur
        ]
        if champs_modifies:
            for champ in champs_modifies:
                setattr(existante, champ, defaults[champ])
            existante.save(update_fields=champs_modifies)

        reenvoi_heures = ALERTES_MVP[type_alerte]["reenvoi_heures"]
        if reenvoi_heures is None:
            return existante, False, False

        delai_ecoule = (
            existante.date_dernier_envoi is None
            or timezone.now() - existante.date_dernier_envoi >= timedelta(hours=reenvoi_heures)
        )
        if not delai_ecoule:
            return existante, False, False

        existante.nombre_envois += 1
        existante.date_dernier_envoi = timezone.now()
        existante.save(update_fields=["nombre_envois", "date_dernier_envoi"])
        return existante, False, True

    @staticmethod
    def cloturer_si_resolue(type_alerte, cles_identification_actives, champ_cle=None):
        """Clôture (RESOLUE) toute Alerte ACTIVE de ce type dont les clés d'identification
        n'apparaissent plus dans cles_identification_actives (liste de dicts, une par
        situation encore constatée lors du run courant).

        champ_cle : à préciser quand un même type_alerte mélange plusieurs familles de
        clés (ex. "activite" regroupée par superviseur ET individuelle par agent) — sans
        cela, une famille de clés vide fermerait à tort les alertes de l'autre famille
        (leur champ de clé absent vaudrait toujours None, jamais présent dans les
        situations actives de l'autre famille). Restreint alors le queryset aux alertes
        où ce champ est renseigné, et ignore les clés des situations elles-mêmes.
        """
        if champ_cle is not None:
            cles_suivies = [champ_cle]
            alertes = Alerte.objects.filter(
                type_alerte=type_alerte, statut="ACTIVE", **{f"{champ_cle}__isnull": False}
            )
        else:
            cles_suivies = list(cles_identification_actives[0].keys()) if cles_identification_actives else []
            alertes = Alerte.objects.filter(type_alerte=type_alerte, statut="ACTIVE")

        for alerte in alertes:
            cles_alerte = {champ: getattr(alerte, f"{champ}_id") for champ in cles_suivies}
            if cles_alerte not in [
                {champ: (v.pk if hasattr(v, "pk") else v) for champ, v in situation.items()}
                for situation in cles_identification_actives
            ]:
                alerte.statut = "RESOLUE"
                alerte.date_resolution = timezone.now()
                alerte.save(update_fields=["statut", "date_resolution"])
