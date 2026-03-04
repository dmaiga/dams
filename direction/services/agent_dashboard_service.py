#/core/services/
from core.models import (Agent, Vente, Recouvrement, 
                         VersementBancaire, Depense, DetailDistribution,
                         DistributionAgent,RecouvrementSuperviseur,
                         AffectationLotSuperviseur )


from django.db.models import Max
from django.utils import timezone
from datetime import timedelta, datetime
from django.db.models import Sum, Count, Max, F, DecimalField,Q
from django.db.models import ExpressionWrapper, DecimalField
from decimal import Decimal
from core.models import Agent, Vente
from django.db.models.functions import Coalesce
from django.core.cache import cache





class DashboardAgentAnalysisService:

    @staticmethod
    def get_agents_dashboard_snapshot():
        cache_key = "agents_dashboard:v2"
        cached = cache.get(cache_key)
        if cached:
            return cached

        data = {
            "kpis": DashboardAgentAnalysisService.get_agent_kpis(),

            # stock uniquement agents terrain
            "agents_stock": DashboardAgentAnalysisService.get_agents_with_stock(),

            # activité terrain récente
            "agents_actifs_48h": DashboardAgentAnalysisService.get_agents_vendu_derniere_48h(),

            # finance superviseurs
            "superviseurs_finance": DashboardAgentAnalysisService.get_superviseurs_finance(),

            # finance ROT
            "rots_finance": DashboardAgentAnalysisService.get_rot_finance(),

            # stock superviseurs par produit
            "superviseurs_produits": DashboardAgentAnalysisService.get_superviseurs_produits(),
            
            # agents en test
            "agents_en_test": DashboardAgentAnalysisService.get_agents_en_test(),

        }

        cache.set(cache_key, data, 60 * 3)  # cache 3 minutes
        return data

    @staticmethod
    def get_mois_courant_range():
        now = timezone.now()
        debut = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return debut, now

    @staticmethod
    def get_trimestre_courant_range():
        now = timezone.now()
        trimestre = (now.month - 1) // 3 + 1
        debut_mois = (trimestre - 1) * 3 + 1

        debut = now.replace(
            month=debut_mois,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )

        return debut, now

    @staticmethod
    def get_agent_kpis():
        """KPI globaux agents (excluts direction)"""
        agents_qs = Agent.objects.filter(est_actif=True).exclude(type_agent='stagiaire')
        return {
               "total_agents": agents_qs.count(),
                "agents_terrain": agents_qs.filter(type_agent='terrain').count(),
                "agents_gros": agents_qs.filter(type_agent='agent_gros').count(),
                "superviseurs": agents_qs.filter(type_agent='entrepot').count(),
                "rots": agents_qs.filter(type_agent='rot').count(), 
              }

    @staticmethod
    def get_agents_par_type_direction():
        agents = Agent.objects.filter(
            est_actif=True
        ).exclude(type_agent='stagiaire')

        return {
            "terrain": agents.filter(type_agent='terrain'),
            "gros": agents.filter(type_agent='agent_gros'),
            "superviseurs": agents.filter(type_agent='entrepot'),
            "rots": agents.filter(type_agent='rot'),
        }


    @staticmethod
    def get_agents_vendu_derniere_48h():
        """
        Agents terrain ayant vendu dans les dernières 48h
        VERSION ORM SAFE (Django 5.x)
        """

        limite = timezone.now() - timedelta(hours=72)

        ventes = (
            Vente.objects
            .filter(
               
            agent__type_agent__in=['terrain', 'agent_gros', 'entrepot'],
            agent__est_actif=True,
            date_vente__gte=limite,
            est_supprime=False
            )
            .annotate(
                ca_ligne=ExpressionWrapper(
                    F("quantite") * F("prix_vente_unitaire"),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                )
            )
            .values("agent_id")
            .annotate(
                nombre_ventes=Count("id"),
                quantite=Sum("quantite"),
                ca=Sum("ca_ligne"),
                derniere_vente=Max("date_vente"),
            )
        )

        agents_map = {
            a.id: a
            for a in Agent.objects.filter(
                id__in=[v["agent_id"] for v in ventes]
            )
        }

        result = []
        for v in ventes:
            agent = agents_map.get(v["agent_id"])
            if not agent:
                continue

            result.append({
                "agent": agent,
                "nombre_ventes": v["nombre_ventes"] or 0,
                "quantite": v["quantite"] or 0,
                "ca": v["ca"] or Decimal("0"),
                "derniere_vente": v["derniere_vente"],
            })

        return result

    @staticmethod
    def get_agents_with_stock():
        """
        Agents terrain avec stock + valeur + argent à recouvrer
        OPTIMISÉ : 4 requêtes max
        """

        # -------------------------
        # Agents terrain
        # -------------------------
        agents = (
            Agent.objects
            .filter(type_agent__in=['terrain', 'agent_gros','entrepot'], 
                    est_actif=True
                    )
            .select_related('user')
        )
        agent_map = {a.id: a for a in agents}

        if not agent_map:
            return []

        agent_ids = list(agent_map.keys())

        # -------------------------
        # Détails de distribution (1 requête)
        # -------------------------
        details = (
            DetailDistribution.objects
            .filter(
                distribution__agent_terrain_id__in=agent_ids,
              
                quantite__gt=0
            )
            .select_related(
                'lot__produit',
                'distribution'
            )
            .annotate(
                quantites_vendue=Coalesce(
                    Sum(
                        'vente__quantite',
                        filter=Q(vente__est_supprime=False)
                    ),
                    Decimal('0.00')
                )
            )
        )

        # -------------------------
        # Recouvrements par agent (1 requête)
        # -------------------------
        debut, fin = DashboardAgentAnalysisService.get_mois_courant_range()
        recouvrements = {
            r["agent_id"]: r["total"]
            for r in (
                Recouvrement.objects
                .filter(
                        agent_id__in=agent_ids,
                        date_recouvrement__gte=debut,
                        date_recouvrement__lte=fin
                        )
                .values("agent_id")
                .annotate(total=Coalesce(Sum("montant_recouvre"), Decimal("0.00")))
            )
        }

        # -------------------------
        # Assemblage Python (ZÉRO SQL)
        # -------------------------
        result = {}
        for agent in agents:
            result[agent.id] = {
                "agent": agent,
                "details": [],
                "valeur_stock": Decimal("0.00"),
                "montant_a_recouvrer": max(
                    agent.total_ventes - recouvrements.get(agent.id, Decimal("0.00")),
                    Decimal("0.00")
                ),
            }

        for d in details:
            reste = d.quantite - d.quantites_vendue
            if reste <= 0:
                continue

            valeur = reste * (d.prix_gros or 0)

            bucket = result[d.distribution.agent_terrain_id]
            bucket["valeur_stock"] += valeur

            bucket["details"].append({
                "distribution_date": d.distribution.date_distribution,
                "produit": d.lot.produit.nom,
                "quantite_restante": reste,
                "prix_gros": d.prix_gros,
                "valeur": valeur,
                "lot": d.lot.reference_lot,
            })

        return [v for v in result.values() if v["details"]]

    @staticmethod
    def get_superviseurs_finance():

        debut, fin = DashboardAgentAnalysisService.get_trimestre_courant_range()

        superviseurs = (
            Agent.objects
            .select_related("user")
            .filter(type_agent='entrepot', est_actif=True)
        )

        ventes_map = {
            x["agent_id"]: x["total"]
            for x in (
                Vente.objects
                .filter(
                    date_vente__range=(debut, fin),
                    est_supprime=False
                )
                .values("agent_id")
                .annotate(
                    total=Coalesce(
                        Sum(
                            ExpressionWrapper(
                                F("quantite") * F("prix_vente_unitaire"),
                                output_field=DecimalField()
                            )
                        ),
                        Decimal("0.00")
                    )
                )
            )
        }

        recouvre_map = {
            x["superviseur_id"]: x["total"]
            for x in (
                Recouvrement.objects
                .filter(date_recouvrement__range=(debut, fin))
                .values("superviseur_id")
                .annotate(total=Coalesce(Sum("montant_recouvre"), Decimal("0.00")))
            )
        }

        remis_map = {
            x["superviseur_id"]: x["total"]
            for x in (
                RecouvrementSuperviseur.objects
                .filter(date_recouvrement__range=(debut, fin))
                .values("superviseur_id")
                .annotate(total=Coalesce(Sum("montant"), Decimal("0.00")))
            )
        }

        data = []

        for sup in superviseurs:

            ventes_perso = ventes_map.get(sup.id, Decimal("0"))
            recouvre_agents = recouvre_map.get(sup.id, Decimal("0"))
            remis_rot = remis_map.get(sup.id, Decimal("0"))

            solde = (recouvre_agents + ventes_perso) - remis_rot

            data.append({
                "superviseur": sup,
                "ventes_personnelles_trimestre": ventes_perso,
                "recouvrements_agents_trimestre": recouvre_agents,
                "solde_trimestre": solde,
            })

        return data

    @staticmethod
    def get_agents_with_stock_cached():
        key = "agents_stock:v1"
        cached = cache.get(key)
        if cached:
            return cached
    
        data = DashboardAgentAnalysisService.get_agents_with_stock()
        cache.set(key, data, 60 * 2)
        return data
    
    @staticmethod
    def get_rot_finance():

        debut, fin = DashboardAgentAnalysisService.get_trimestre_courant_range()

        rots = Agent.objects.select_related("user").filter(
            type_agent='rot',
            est_actif=True
        )

        recup_map = {
            x["rot_id"]: x["total"]
            for x in (
                RecouvrementSuperviseur.objects
                .filter(date_recouvrement__range=(debut, fin))
                .values("rot_id")
                .annotate(total=Coalesce(Sum("montant"), Decimal("0.00")))
            )
        }

        verse_map = {
            x["effectue_par_id"]: x["total"]
            for x in (
                VersementBancaire.objects
                .filter(date_versement_reelle__range=(debut, fin))
                .values("effectue_par_id")
                .annotate(total=Coalesce(Sum("montant_vente"), Decimal("0.00")))
            )
        }

        depense_map = {
            x["effectue_par_id"]: x["total"]
            for x in (
                Depense.objects
                .filter(date_depense__range=(debut, fin))
                .values("effectue_par_id")
                .annotate(total=Coalesce(Sum("montant"), Decimal("0.00")))
            )
        }

        data = []

        for rot in rots:

            recupere = recup_map.get(rot.id, Decimal("0"))
            verse = verse_map.get(rot.id, Decimal("0"))
            depenses = depense_map.get(rot.id, Decimal("0"))
            ajustement = rot.ajustement_solde or Decimal('0')

            solde_trimestre = (
                recupere
                - verse
                - depenses
                + ajustement
            )
            data.append({
                "rot": rot,
                "recupere_trimestre": recupere,
                "verse_trimestre": verse,
                "depenses_trimestre": depenses,
                "solde_trimestre": solde_trimestre,
            })

        return data

    @staticmethod
    def get_superviseurs_produits():
        superviseurs = Agent.objects.filter(
            type_agent='entrepot',
            est_actif=True
        ).select_related('user')

        affectations = (
            AffectationLotSuperviseur.objects
            .filter(superviseur__in=superviseurs, quantite_restante__gt=0)
            .select_related('lot__produit', 'superviseur')
            .order_by('-date_affectation')
        )

        data = {}
        for aff in affectations:
            sid = aff.superviseur.id
            data.setdefault(sid, {
                "superviseur": aff.superviseur,
                "produits": []
            })

            data[sid]["produits"].append({
                "produit": aff.lot.produit.nom,
                "lot": aff.lot.reference_lot,
                "quantite_restante": aff.quantite_restante,
                "quantite_initiale": aff.quantite_initiale,
                "date_affectation": aff.date_affectation,
            })

        return list(data.values())


# core/services/agent_dashboard_service.py

    @staticmethod
    def get_agents_en_test():
    
        today = timezone.now().date()
        debut_global = today - timedelta(days=14)
    
        # ✅ agents chargés avec user + superviseur
        agents = list(
            Agent.objects
            .select_related("user", "superviseur__user")
            .filter(
                est_actif=True,
                type_agent__in=["terrain", "agent_gros"],
                date_debut_fonction__isnull=False,
                date_debut_fonction__gte=debut_global
            )
        )
    
        if not agents:
            return []
    
        agent_ids = [a.id for a in agents]
    
        # ✅ expression KG unique
        kg_expression = ExpressionWrapper(
            F("quantite") *
            Coalesce(
                F("detail_distribution__lot__produit__poids_unitaire_kg"),
                Decimal("1.0")
            ),
            output_field=DecimalField(max_digits=14, decimal_places=2)
        )
    
        # ✅ UNE SEULE REQUÊTE ventes
        ventes_agg = {
            x["agent_id"]: x["total"]
            for x in (
                Vente.objects
                .filter(
                    agent_id__in=agent_ids,
                    est_supprime=False,
                    date_vente__date__gte=debut_global
                )
                .annotate(kg=kg_expression)
                .values("agent_id")
                .annotate(
                    total=Coalesce(
                        Sum("kg"),
                        Decimal("0.00"),
                        output_field=DecimalField(max_digits=14, decimal_places=2)
                    )
                )
            )
        }
    
        result = []
    
        for agent in agents:
        
            debut = agent.date_debut_fonction
            total_kg = ventes_agg.get(agent.id, Decimal("0.00"))
    
            nb_jours = max((today - debut).days, 1)
            kg_par_jour = total_kg / Decimal(nb_jours)
    
            # 🎯 Evaluation performance
            if kg_par_jour >= 50:
                statut = "conforme"
                couleur = "success"
            elif kg_par_jour >= 30:
                statut = "tolere"
                couleur = "warning"
            else:
                statut = "insuffisant"
                couleur = "danger"
    
            jours_restants = max(
                14 - (today - debut).days,
                0
            )
    
            result.append({
                "agent": agent,
                "superviseur": agent.superviseur,
                "date_debut": debut,
                "jours_restants": jours_restants,
                "total_kg": total_kg,
                "kg_par_jour": round(kg_par_jour, 2),
                "statut": statut,
                "couleur": couleur,
            })
    
        return result
    