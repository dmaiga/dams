#/core/services/
from core.models import (Agent, Vente, Recouvrement, 
                         VersementBancaire, Depense, DetailDistribution,
                         DistributionAgent,RecouvrementSuperviseur)

from django.db.models import Max
from django.utils import timezone
from datetime import timedelta, datetime
from django.db.models import Sum, Count, Max, F, DecimalField,Q
from django.db.models import ExpressionWrapper, DecimalField

from decimal import Decimal

from core.models import Agent, Vente

from django.db.models.functions import Coalesce

from django.core.cache import cache

class AgentAnalysisService:
    
    @staticmethod
    def get_mois_courant_range():
        now = timezone.now()
        debut = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
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
    def get_agents_direction_view():
        ventes = (
            Vente.objects
            .filter(stagiaire__isnull=True, est_supprime=False)
            .values("agent_id", "agent__type_agent")
            .annotate(
                ca=Sum(F("quantite") * F("prix_vente_unitaire")),
                quantite=Sum("quantite"),
                derniere_vente=Max("date_vente"),
            )
        )

        agents_map = {
            a.id: a
            for a in Agent.objects.exclude(type_agent='stagiaire').select_related("user")
        }

        result = []

        for v in ventes:
            agent = agents_map.get(v["agent_id"])
            if not agent:
                continue

            result.append({
                "agent": agent,
                "type_agent": agent.type_agent,
                "ca": v["ca"] or Decimal("0"),
                "quantite": v["quantite"] or 0,
                "argent_possession": agent.argent_en_possession,
                "derniere_vente": v["derniere_vente"],
            })

        return result

    @staticmethod
    def get_direction_kpis():
        ventes = Vente.objects.filter(
            stagiaire__isnull=True,
            est_supprime=False
        )

        versements = VersementBancaire.objects.all()
        depenses = Depense.objects.all()

        return {
            "ca_total": ventes.aggregate(
                total=Coalesce(
                    Sum(F("quantite") * F("prix_vente_unitaire")),
                    Decimal("0")
                )
            )["total"],

            "total_verse": versements.aggregate(
                total=Coalesce(Sum("montant_vente"), Decimal("0"))
            )["total"],

            "total_depenses": depenses.aggregate(
                total=Coalesce(Sum("montant"), Decimal("0"))
            )["total"],

            "nombre_versements": versements.count(),
        }


    @staticmethod
    def get_superviseurs_finance():
        debut, fin = AgentAnalysisService.get_mois_courant_range()

        superviseurs = Agent.objects.filter(type_agent='entrepot', est_actif=True)

        data = []
        for sup in superviseurs:

            ventes_perso = Vente.objects.filter(
                agent=sup,
                date_vente__gte=debut,
                date_vente__lte=fin,
                est_supprime=False
            ).aggregate(
                total=Coalesce(
                    Sum(F("quantite") * F("prix_vente_unitaire")),
                    Decimal("0")
                )
            )["total"]

            recouvre_agents = Recouvrement.objects.filter(
                superviseur=sup,
                date_recouvrement__gte=debut,
                date_recouvrement__lte=fin
            ).aggregate(
                total=Coalesce(Sum("montant_recouvre"), Decimal("0"))
            )["total"]

            solde = ventes_perso + recouvre_agents

            data.append({
                "superviseur": sup,
                "ventes_personnelles": ventes_perso,
                "recouvrements_agents": recouvre_agents,
                "solde_mois": solde,
            })

        return data

    @staticmethod
    def get_encadrement_financier_mensuel():
        """
        Vue direction – synthèse mensuelle
        Superviseurs + ROT
        """
        today = timezone.now().date()
        debut_mois = today.replace(day=1)

        data = []

        # =========================
        # SUPERVISEURS
        # =========================
        superviseurs = Agent.objects.filter(type_agent='entrepot', est_actif=True)

        for sup in superviseurs:
            # ventes personnelles autorisées (mois)
            ventes_perso = Vente.objects.filter(
                agent=sup,
                date_vente__date__gte=debut_mois
            ).aggregate(
                total=Coalesce(
                    Sum(F("quantite") * F("prix_vente_unitaire")),
                    Decimal("0")
                )
            )["total"]

            # recouvrements agents (mois)
            recouvre_agents = Recouvrement.objects.filter(
                superviseur=sup,
                date_recouvrement__date__gte=debut_mois
            ).aggregate(
                total=Coalesce(Sum("montant_recouvre"), Decimal("0"))
            )["total"]

            # remis au ROT (mois)
            remis_rot = RecouvrementSuperviseur.objects.filter(
                superviseur=sup,
                date_creation__date__gte=debut_mois
            ).aggregate(
                total=Coalesce(Sum("montant"), Decimal("0"))
            )["total"]

            cash_detenu = ventes_perso + recouvre_agents - remis_rot

            data.append({
                "agent": sup,
                "role": "Superviseur",
                "ventes": ventes_perso,
                "recouvre": recouvre_agents,
                "verse": remis_rot,
                "solde": cash_detenu,
            })

        # =========================
        # ROT
        # =========================
        rots = Agent.objects.filter(type_agent='rot', est_actif=True)

        for rot in rots:
            recu_sup = RecouvrementSuperviseur.objects.filter(
                rot=rot,
                date_creation__date__gte=debut_mois
            ).aggregate(
                total=Coalesce(Sum("montant"), Decimal("0"))
            )["total"]

            verse_banque = VersementBancaire.objects.filter(
                effectue_par=rot,
                date_versement_reelle__date__gte=debut_mois
            ).aggregate(
                total=Coalesce(Sum("montant_vente"), Decimal("0"))
            )["total"]

            solde = recu_sup - verse_banque

            data.append({
                "agent": rot,
                "role": "ROT",
                "ventes": Decimal("0"),
                "recouvre": recu_sup,
                "verse": verse_banque,
                "solde": solde,
            })

        return data

    @staticmethod
    def resolve_period(request):
        periode = request.GET.get("periode", "mois")
        today = timezone.now().date()

        if periode == "mois_prec":
            debut = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
            fin = today.replace(day=1) - timedelta(days=1)

        elif periode == "custom":
            debut = request.GET.get("date_debut")
            fin = request.GET.get("date_fin")
            if debut and fin:
                debut = datetime.strptime(debut, "%Y-%m-%d").date()
                fin = datetime.strptime(fin, "%Y-%m-%d").date()
            else:
                debut = today.replace(day=1)
                fin = today

        else:  # mois courant
            debut = today.replace(day=1)
            fin = today

        return {
            "periode": periode,
            "date_debut": debut,
            "date_fin": fin,
        }



    @staticmethod
    def get_superviseur_detail(superviseur, debut, fin):
        # ======================
        # AGENTS SUPERVISÉS
        # ======================
        agents = Agent.objects.filter(
            superviseur=superviseur,
            est_actif=True
        ).exclude(type_agent='stagiaire')

        agents_data = []
        total_ca = Decimal("0")
        total_quantite = 0
        total_marge = Decimal("0")
        qte_gros = 0
        qte_detail = 0

        for agent in agents:
            ventes = Vente.objects.filter(
                agent=agent,
                date_vente__date__range=(debut, fin),
                est_supprime=False
            )

            # CA calculation
            agg = ventes.aggregate(
                ca=Coalesce(
                    Sum(
                        F("quantite") * F("prix_vente_unitaire"),
                        output_field=DecimalField(max_digits=15, decimal_places=2)
                    ),
                    Decimal("0")
                ),
                quantite=Coalesce(
                    Sum("quantite", output_field=DecimalField(max_digits=10, decimal_places=2)),
                    0
                ),
            )


            marge = ventes.aggregate(
                marge=Coalesce(
                    Sum(
                        (
                            F("prix_vente_unitaire") -
                            Coalesce(
                                F("detail_distribution__lot__prix_achat_unitaire"),
                                Decimal("0.00"),
                                output_field=DecimalField(max_digits=10, decimal_places=2)
                            )
                        ) * F("quantite"),
                        output_field=DecimalField(max_digits=15, decimal_places=2)
                    ),
                    Decimal("0.00")
                )
            )["marge"]


            recouvre = Recouvrement.objects.filter(
                agent=agent,
                superviseur=superviseur,
                date_recouvrement__date__range=(debut, fin)
            ).aggregate(
                total=Coalesce(
                    Sum("montant_recouvre", output_field=DecimalField(max_digits=10, decimal_places=2)),
                    Decimal("0")
                )
            )["total"]

            reste = agg["ca"] - recouvre

            if agent.est_agent_gros:
                qte_gros += agg["quantite"]
            else:
                qte_detail += agg["quantite"]

            total_ca += agg["ca"]
            total_quantite += agg["quantite"]
            total_marge += marge

            agents_data.append({
                "agent": agent,
                "type": "Grossiste" if agent.est_agent_gros else "Détaillant",
                "ca": agg["ca"],
                "quantite": agg["quantite"],
                "marge": marge,
                "reste": reste,
            })

        # ======================
        # FLUX SUPERVISEUR
        # ======================
        recouvre_agents = Recouvrement.objects.filter(
            superviseur=superviseur,
            date_recouvrement__date__range=(debut, fin)
        ).aggregate(
            total=Coalesce(
                Sum("montant_recouvre", output_field=DecimalField(max_digits=10, decimal_places=2)),
                Decimal("0")
            )
        )["total"]

        # Fix ventes_perso aggregation
        ventes_perso = Vente.objects.filter(
            agent=superviseur,
            date_vente__date__range=(debut, fin)
        ).aggregate(
            total=Coalesce(
                Sum(
                    F("quantite") * F("prix_vente_unitaire"),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                ),
                Decimal("0")
            )
        )["total"]

        remis_rot = VersementBancaire.objects.filter(
            superviseur=superviseur,
            date_versement_reelle__date__range=(debut, fin)
        ).aggregate(
            total=Coalesce(
                Sum("montant_vente", output_field=DecimalField(max_digits=10, decimal_places=2)),
                Decimal("0")
            )
        )["total"]

        cash_detenu = recouvre_agents + ventes_perso
        solde = cash_detenu - remis_rot

        return {
            "superviseur": superviseur,

            # KPIs business
            "kpis": {
                "ca_total": total_ca,
                "quantite": total_quantite,
                "marge": total_marge,
                "taux_marge": round((total_marge / total_ca) * 100, 1) if total_ca > 0 else 0,
                "mix_gros": round((qte_gros / total_quantite) * 100, 1) if total_quantite else 0,
                "mix_detail": round((qte_detail / total_quantite) * 100, 1) if total_quantite else 0,
                "solde": solde,
            },

            # flux
            "flux": {
                "recouvre_agents": recouvre_agents,
                "ventes_perso": ventes_perso,
                "remis_rot": remis_rot,
                "cash_detenu": cash_detenu,
            },

            "agents": agents_data,
        }

    @staticmethod
    def get_superviseur_sales_kpis(superviseur, debut, fin):
        ventes = Vente.objects.filter(
            agent__superviseur=superviseur,
            date_vente__date__range=(debut, fin),
            stagiaire__isnull=True,
            est_supprime=False
        )

        agg = ventes.aggregate(
            ca=Coalesce(Sum(F("quantite") * F("prix_vente_unitaire")), Decimal("0")),
            quantite=Coalesce(Sum("quantite"), 0),
            marge=Coalesce(
                Sum(
                    (F("prix_vente_unitaire") - F("detail_distribution__lot__prix_achat_unitaire"))
                    * F("quantite")
                ),
                Decimal("0")
            ),
        )

        qte_gros = ventes.filter(type_vente='gros').aggregate(
            q=Coalesce(Sum("quantite"), 0)
        )["q"]

        qte_detail = ventes.filter(type_vente='detail').aggregate(
            q=Coalesce(Sum("quantite"), 0)
        )["q"]

        total_qte = agg["quantite"] or 0

        return {
            "ca_total": agg["ca"],
            "quantite": total_qte,
            "marge": agg["marge"],
            "taux_marge": round((agg["marge"] / agg["ca"] * 100), 1) if agg["ca"] > 0 else 0,
            "mix_gros": round((qte_gros / total_qte) * 100, 1) if total_qte else 0,
            "mix_detail": round((qte_detail / total_qte) * 100, 1) if total_qte else 0,
        }

    @staticmethod
    def get_rot_detail(rot, debut, fin):
        recu = RecouvrementSuperviseur.objects.filter(
            rot=rot,
            date_recouvrement__date__range=(debut, fin)
        ).aggregate(
            total=Coalesce(Sum("montant"), Decimal("0"))
        )["total"]

        verse = VersementBancaire.objects.filter(
            effectue_par=rot,
            date_versement_reelle__date__range=(debut, fin)
        ).aggregate(
            total=Coalesce(Sum("montant_vente"), Decimal("0"))
        )["total"]

        depenses = Depense.objects.filter(
            effectue_par=rot,
            date_depense__date__range=(debut, fin)
        ).aggregate(
            total=Coalesce(Sum("montant"), Decimal("0"))
        )["total"]

        return {
            "rot": rot,
            "recu": recu,
            "verse": verse,
            "depenses": depenses,
            "solde": recu - verse - depenses,
        }

    @staticmethod
    def get_agent_regularity_status(jours_inactifs):
        """Détermine le statut de régularité basé sur les jours d'inactivité"""
        if jours_inactifs == "Aucune vente":
            return 'red'
        
        if jours_inactifs < 3:
            return 'green'
        elif 3 <= jours_inactifs <= 7:  
            return 'orange'
        else:
            return 'red'

    @staticmethod
    def get_agent_global_data(agent):
        """Données globales (non filtrées par période)"""
        ventes = Vente.objects.filter(agent=agent, stagiaire__isnull=True)
        
        total_ventes = ventes.count()
        total_quantite = sum(vente.quantite for vente in ventes)
        total_ca = sum(vente.total_vente for vente in ventes)
        
        # Dernière vente
        derniere_vente = ventes.order_by('-date_vente').first()
        jours_depuis_derniere_vente = "Aucune vente"
        if derniere_vente:
            aujourd_hui = timezone.now().date()
            date_vente = derniere_vente.date_vente
            if isinstance(date_vente, datetime):
                date_vente = date_vente.date()
            jours_depuis_derniere_vente = (aujourd_hui - date_vente).days
        
        # 7 derniers jours
        date_7_jours = timezone.now() - timedelta(days=7)
        ventes_7_jours = ventes.filter(date_vente__gte=date_7_jours)
        quantite_7_jours = sum(vente.quantite for vente in ventes_7_jours)
        
        # Calcul du statut de régularité cohérent
        regularity_status = AgentAnalysisService.get_agent_regularity_status(jours_depuis_derniere_vente)
        
        return {
            'total_ventes': total_ventes,
            'total_quantite': total_quantite,
            'total_ca': total_ca,
            'jours_depuis_derniere_vente': jours_depuis_derniere_vente,
            'quantite_7_jours': quantite_7_jours,
            'regularity_status': regularity_status,
            'derniere_vente_date': derniere_vente.date_vente if derniere_vente else None,
        }

    @staticmethod
    def get_agent_current_stock(agent):
        """Récupère les produits actuellement à disposition de l'agent"""
        distributions_actives = DistributionAgent.objects.filter(
            agent_terrain=agent
            
        )
        
        stock_data = []
        total_produits = 0
        
        for distribution in distributions_actives:
            details = distribution.detaildistribution_set.all()
            
            for detail in details:
                quantite_restante = detail.quantite_restante_calculee
                if quantite_restante > 0:
                    total_produits += 1
                    stock_data.append({
                        'distribution_date': distribution.date_distribution,
                        'produit': detail.lot.produit.nom,
                        'quantite_initiale': detail.quantite,
                        'quantite_restante': quantite_restante,
                        'prix_gros': detail.prix_gros,
                        'prix_detail': detail.prix_detail,
                        'specification': detail.specification,
                        'lot': detail.lot,
                    })
        
        return {
            'stock_details': stock_data,
            'total_produits_disponibles': total_produits,
        }

    @staticmethod
    def get_period_dates(period_type='monthly'):
        """Retourne les dates de début et fin pour une période donnée"""
        aujourd_hui = timezone.now()
        
        if period_type == 'daily':
            date_debut = aujourd_hui.replace(hour=0, minute=0, second=0, microsecond=0)
            date_fin = date_debut + timedelta(days=1)
        elif period_type == 'weekly':
            date_debut = aujourd_hui - timedelta(days=aujourd_hui.weekday())
            date_debut = date_debut.replace(hour=0, minute=0, second=0, microsecond=0)
            date_fin = date_debut + timedelta(days=7)
        elif period_type == 'yearly':
            date_debut = aujourd_hui.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            date_fin = date_debut.replace(year=date_debut.year + 1)
        else:  # monthly (par défaut)
            date_debut = aujourd_hui.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if aujourd_hui.month == 12:
                date_fin = date_debut.replace(year=date_debut.year + 1, month=1)
            else:
                date_fin = date_debut.replace(month=date_debut.month + 1)
        
        return date_debut, date_fin
            
    @staticmethod
    def get_agent_period_data(agent, period_type='monthly'):
        """Retourne toutes les données pour une période donnée"""
        date_debut, date_fin = AgentAnalysisService.get_period_dates(period_type)
        
        # Ventes personnelles pour la période
        ventes_periode = Vente.objects.filter(
            agent=agent,
            stagiaire__isnull=True,
            date_vente__gte=date_debut,
            date_vente__lt=date_fin
        )
        
        # Calculs de base
        nombre_ventes = ventes_periode.count()
        quantite_vendue = sum(vente.quantite for vente in ventes_periode)
        ca_total = sum(vente.total_vente for vente in ventes_periode)
        
        # Calcul de la marge
        marge_totale = Decimal('0')
        for vente in ventes_periode:
            prix_achat = vente.detail_distribution.lot.prix_achat_unitaire or Decimal('0')
            marge_vente = (vente.prix_vente_unitaire - prix_achat) * vente.quantite
            marge_totale += marge_vente
        
        taux_marge = (marge_totale / ca_total * 100) if ca_total > 0 else 0
        
        # Répartition par type de vente
        ventes_gros = ventes_periode.filter(type_vente='gros')
        ventes_detail = ventes_periode.filter(type_vente='detail')
        
        quantite_gros = sum(vente.quantite for vente in ventes_gros)
        quantite_detail = sum(vente.quantite for vente in ventes_detail)
        ca_gros = sum(vente.total_vente for vente in ventes_gros)
        ca_detail = sum(vente.total_vente for vente in ventes_detail)
        
        pourcentage_gros = (quantite_gros / quantite_vendue * 100) if quantite_vendue > 0 else 0
        pourcentage_detail = (quantite_detail / quantite_vendue * 100) if quantite_vendue > 0 else 0
        
        return {
            'period_type': period_type,
            'date_debut': date_debut,
            'date_fin': date_fin,
            'nombre_ventes': nombre_ventes,
            'quantite_vendue': quantite_vendue,
            'ca_total': ca_total,
            'marge_totale': marge_totale,
            'taux_marge': round(taux_marge, 1),
            'quantite_gros': quantite_gros,
            'quantite_detail': quantite_detail,
            'ca_gros': ca_gros,
            'ca_detail': ca_detail,
            'pourcentage_gros': round(pourcentage_gros, 1),
            'pourcentage_detail': round(pourcentage_detail, 1),
        }   


    @staticmethod
    def get_agents_terrain_performance(mois='all'):
        """
        VERSION PRO – CONTRAT STABLE POUR LE TEMPLATE
        """

        # -------------------------
        # Filtre ventes
        # -------------------------
        ventes_filter = Q(
            agent__type_agent='terrain',
            stagiaire__isnull=True,
            est_supprime=False
        )

        if mois != 'all':
            try:
                jours = int(mois)
                ventes_filter &= Q(
                    date_vente__gte=timezone.now() - timedelta(days=jours)
                )
            except ValueError:
                pass

        # -------------------------
        # 1️⃣ AGRÉGATS SQL
        # -------------------------
        ventes = (
            Vente.objects
            .filter(ventes_filter)
            .values("agent_id")
            .annotate(
                total_quantite=Sum("quantite"),

                total_ca=Sum(
                    F("quantite") * F("prix_vente_unitaire"),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                ),

                marge_totale=Sum(
                    (F("prix_vente_unitaire") - F("detail_distribution__lot__prix_achat_unitaire"))
                    * F("quantite"),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                ),

                quantite_gros=Sum(
                    "quantite",
                    filter=Q(type_vente='gros')
                ),
                quantite_detail=Sum(
                    "quantite",
                    filter=Q(type_vente='detail')
                ),

                derniere_vente=Max("date_vente"),
            )
        )

        ventes_map = {v["agent_id"]: v for v in ventes}

        # -------------------------
        # 2️⃣ AGENTS ORM
        # -------------------------
        agents = (
            Agent.objects
            .filter(type_agent='terrain', est_actif=True)
            
            .select_related("user")
        )

        now = timezone.now()
        result = []

        # -------------------------
        # 3️⃣ VIEW MODEL FINAL
        # -------------------------
        for agent in agents:
            stats = ventes_map.get(agent.id)

            if not stats:
                # agent sans vente
                result.append({
                    "agent": agent,
                    "total_ca": Decimal("0"),
                    "marge_totale": Decimal("0"),
                    "total_quantite": 0,
                    "repartition": "-",
                    "derniere_vente": None,
                    "jours_depuis_derniere_vente": "Aucune vente",
                    "argent_possession": agent.argent_en_possession,
                })
                continue

            qte_total = stats["total_quantite"] or 0
            qte_gros = stats["quantite_gros"] or 0
            qte_detail = stats["quantite_detail"] or 0

            repartition = "-"
            if qte_total > 0:
                repartition = (
                    f"{round(qte_gros / qte_total * 100)}% / "
                    f"{round(qte_detail / qte_total * 100)}%"
                )

            derniere_vente = stats["derniere_vente"]
            jours_inactifs = (
                (now - derniere_vente).days
                if derniere_vente else "Aucune vente"
            )

            result.append({
                "agent": agent,
                "total_ca": stats["total_ca"] or Decimal("0"),
                "marge_totale": stats["marge_totale"] or Decimal("0"),
                "total_quantite": qte_total,
                "repartition": repartition,
                "derniere_vente": derniere_vente,
                "jours_depuis_derniere_vente": jours_inactifs,
                "argent_possession": agent.argent_en_possession,
            })

        return result

    @staticmethod
    def get_agents_terrain_performance_weekly():
        now = timezone.now()
        debut_semaine = now - timedelta(days=7)

        # -------------------------
        # FILTRES
        # -------------------------
        base_filter = Q(
            agent__type_agent='terrain',
            stagiaire__isnull=True,
            est_supprime=False
        )

        semaine_filter = base_filter & Q(date_vente__gte=debut_semaine)

        # -------------------------
        # AGRÉGATS GLOBAUX
        # -------------------------
        global_stats = (
            Vente.objects
            .filter(base_filter)
            .values("agent_id")
            .annotate(
                total_ca=Sum(
                    F("quantite") * F("prix_vente_unitaire"),
                    output_field=DecimalField()
                ),
                marge_totale=Sum(
                    (F("prix_vente_unitaire") - F("detail_distribution__lot__prix_achat_unitaire"))
                    * F("quantite"),
                    output_field=DecimalField()
                ),
                total_quantite=Sum("quantite"),
                derniere_vente=Max("date_vente"),
            )
        )

        global_map = {g["agent_id"]: g for g in global_stats}

        # -------------------------
        # AGRÉGATS HEBDOMADAIRES
        # -------------------------
        weekly_stats = (
            Vente.objects
            .filter(semaine_filter)
            .values("agent_id")
            .annotate(
                ca_semaine=Sum(
                    F("quantite") * F("prix_vente_unitaire"),
                    output_field=DecimalField()
                ),
                marge_semaine=Sum(
                    (F("prix_vente_unitaire") - F("detail_distribution__lot__prix_achat_unitaire"))
                    * F("quantite"),
                    output_field=DecimalField()
                ),
                quantite_semaine=Sum("quantite"),
                nombre_ventes_semaine=Count("id"),
            )
        )

        weekly_map = {w["agent_id"]: w for w in weekly_stats}

        # -------------------------
        # AGENTS
        # -------------------------
        agents = (
            Agent.objects
            .filter(type_agent='terrain', est_actif=True)
            .select_related("user")
        )

        result = []

        for agent in agents:
            g = global_map.get(agent.id, {})
            w = weekly_map.get(agent.id, {})

            derniere_vente = g.get("derniere_vente")
            jours_inactifs = (
                (now - derniere_vente).days
                if derniere_vente else "Aucune vente"
            )

            result.append({
                "agent": agent,

                # GLOBAL
                "total_ca": g.get("total_ca") or Decimal("0"),
                "marge_totale": g.get("marge_totale") or Decimal("0"),
                "total_quantite": g.get("total_quantite") or 0,
                "derniere_vente": derniere_vente,
                "jours_depuis_derniere_vente": jours_inactifs,
                "argent_possession": agent.argent_en_possession,

                # 🔥 HEBDO
                "total_ca_semaine": w.get("ca_semaine") or Decimal("0"),
                "marge_semaine": w.get("marge_semaine") or Decimal("0"),
                "total_quantite_semaine": w.get("quantite_semaine") or 0,
                "nombre_ventes_semaine": w.get("nombre_ventes_semaine") or 0,
            })

        return result

    @staticmethod
    def get_custom_period_data(agent, date_debut, date_fin):
        """Retourne les données pour une période personnalisée"""
        # Ventes personnelles pour la période personnalisée
        ventes_periode = Vente.objects.filter(
            agent=agent,
            stagiaire__isnull=True,
            date_vente__gte=date_debut,
            date_vente__lt=date_fin
        )

        # Calculs de base
        nombre_ventes = ventes_periode.count()
        quantite_vendue = sum(vente.quantite for vente in ventes_periode)
        ca_total = sum(vente.total_vente for vente in ventes_periode)

        # Calcul de la marge
        marge_totale = Decimal('0')
        for vente in ventes_periode:
            prix_achat = vente.detail_distribution.lot.prix_achat_unitaire or Decimal('0')
            marge_vente = (vente.prix_vente_unitaire - prix_achat) * vente.quantite
            marge_totale += marge_vente

        taux_marge = (marge_totale / ca_total * 100) if ca_total > 0 else 0

        # Répartition par type de vente
        ventes_gros = ventes_periode.filter(type_vente='gros')
        ventes_detail = ventes_periode.filter(type_vente='detail')

        quantite_gros = sum(vente.quantite for vente in ventes_gros)
        quantite_detail = sum(vente.quantite for vente in ventes_detail)
        ca_gros = sum(vente.total_vente for vente in ventes_gros)
        ca_detail = sum(vente.total_vente for vente in ventes_detail)

        pourcentage_gros = (quantite_gros / quantite_vendue * 100) if quantite_vendue > 0 else 0
        pourcentage_detail = (quantite_detail / quantite_vendue * 100) if quantite_vendue > 0 else 0

        return {
            'period_type': 'custom',
            'date_debut': date_debut,
            'date_fin': date_fin,
            'nombre_ventes': nombre_ventes,
            'quantite_vendue': quantite_vendue,
            'ca_total': ca_total,
            'marge_totale': marge_totale,
            'taux_marge': round(taux_marge, 1),
            'quantite_gros': quantite_gros,
            'quantite_detail': quantite_detail,
            'ca_gros': ca_gros,
            'ca_detail': ca_detail,
            'pourcentage_gros': round(pourcentage_gros, 1),
            'pourcentage_detail': round(pourcentage_detail, 1),
        }

    @staticmethod
    def get_agent_detailed_analysis(agent, period_filter='yearly', date_debut=None, date_fin=None):
        """Analyse détaillée complète avec support période personnalisée"""
        if period_filter == 'custom' and date_debut and date_fin:
            period_data = AgentAnalysisService.get_custom_period_data(agent, date_debut, date_fin)
        else:
            period_data = AgentAnalysisService.get_agent_period_data(agent, period_filter)

        global_data = AgentAnalysisService.get_agent_global_data(agent)
        stock_data = AgentAnalysisService.get_agent_current_stock(agent)

        return {
            'period_data': period_data,
            'global_data': global_data,
            'stock_data': stock_data,
            'argent_possession': agent.argent_en_possession,
            'total_recouvre': agent.total_recouvre,
            'nombre_ventes_stagiaires': agent.vente_set.filter(stagiaire__isnull=False).count(),
        }

