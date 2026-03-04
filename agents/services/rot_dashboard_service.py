from decimal import Decimal
from django.db.models import Sum, F, DecimalField
from django.db.models.functions import Coalesce
from requests import request
from agents.services.rot_fournisseur import RotFournisseurService
from core.models import (
    Agent,
    Vente,
    RecouvrementSuperviseur,
    Recouvrement,
    VersementBancaire,
    Depense,
    ClotureMensuelle,
    LotEntrepot,
    AffectationLotSuperviseur,
    Fournisseur,
      PaiementFournisseur,
    )
from django.db.models import ExpressionWrapper
from django.conf import settings

def get_date_debut_rot():
    return settings.DATE_DEBUT_ROT


from django.utils import timezone

def get_debut_mois():
    now = timezone.now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

 

class RotDashboardService:

    SEUIL_STOCK_FAIBLE = Decimal("10.00")

    @staticmethod
    def get_stock_entrepot():
        """
        Stock entrepôt – Dashboard ROT
        1) valeur_ligne = quantite_restante × prix_achat_unitaire
        2) somme(valeur_ligne) par produit
        """
    
        lots_annotes = (
            LotEntrepot.objects
            .annotate(
                valeur_ligne=ExpressionWrapper(
                    F('quantite_restante') * F('prix_achat_unitaire'),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                )
            )
        )
    
        produits = (
            lots_annotes
            .values('produit__nom')
            .annotate(
                quantite_restante=Coalesce(
                    Sum('quantite_restante'),
                    Decimal('0.00')
                ),
                valeur_stock=Coalesce(
                    Sum('valeur_ligne'),
                    Decimal('0.00')
                )
            )
            .order_by('produit__nom')
        )
    
        return {
            'produits': produits,
            'seuil_faible': RotDashboardService.SEUIL_STOCK_FAIBLE
        }

    # =====================================================
    # 1️⃣ KPIs GLOBAUX ROT
    # =====================================================
    @staticmethod
    def get_kpis(rot):
    
        if not rot or not rot.est_rot:
            return {
                'total_recupere_rot': Decimal('0'),
                'total_verse_banque': Decimal('0'),
                'total_depenses': Decimal('0'),
                'solde_rot': Decimal('0'),
            }
    
        debut_mois = get_debut_mois()
    
        recouvre_qs = RecouvrementSuperviseur.objects.filter(
            rot=rot,
            date_recouvrement__gte=debut_mois
        )
    
        versement_qs = VersementBancaire.objects.filter(
            effectue_par=rot,
            date_versement_reelle__gte=debut_mois
        )
    
        depense_qs = Depense.objects.filter(
            effectue_par=rot,
            date_depense__gte=debut_mois
        )
    
        total_recupere = recouvre_qs.aggregate(
            total=Coalesce(Sum('montant'), Decimal('0'))
        )['total']
    
        total_verse = versement_qs.aggregate(
            total=Coalesce(Sum('montant_vente'), Decimal('0'))
        )['total']
    
        total_depenses = depense_qs.aggregate(
            total=Coalesce(Sum('montant'), Decimal('0'))
        )['total']
    
        return {
            'total_recupere_rot': total_recupere,
            'total_verse_banque': total_verse,
            'total_depenses': total_depenses,
            'solde_rot' : rot.solde_rot
        }
    
    @staticmethod
    def get_stock_critique():
        """
        Dashboard ROT :
        Affiche uniquement les stocks faibles (< seuil)
        """

        seuil = RotDashboardService.SEUIL_STOCK_FAIBLE

        produits = (
            LotEntrepot.objects
            .values("produit__nom")
            .annotate(
                quantite_restante=Coalesce(
                    Sum("quantite_restante"),
                    Decimal("0.00")
                )
            )
            .filter(quantite_restante__lt=seuil)
            .order_by("quantite_restante")
        )

        produits_faibles = list(produits)

        return {
            "stocks_faibles": produits_faibles,
            "has_alert": len(produits_faibles) > 0,
            "seuil": seuil,
        }

    @staticmethod
    def get_suivi_superviseurs():
        data = []
        debut_mois = get_debut_mois()

        superviseurs = Agent.objects.filter(
            type_agent='entrepot',
            est_actif=True
        )

        for sup in superviseurs:

            # 1️⃣ Argent récupéré auprès des agents (mois en cours)
            total_recouvre_agents = Recouvrement.objects.filter(
                superviseur=sup,
                date_recouvrement__gte=debut_mois
            ).aggregate(
                total=Coalesce(Sum('montant_recouvre'), Decimal('0.00'))
            )['total']

            # 2️⃣ Ventes personnelles du superviseur (mois en cours)
            ventes_superviseur = Vente.objects.filter(
                agent=sup,
                date_vente__gte=debut_mois,
                est_supprime=False
            ).aggregate(
                total=Coalesce(
                    Sum(F('quantite') * F('prix_vente_unitaire')),
                    Decimal('0.00')
                )
            )['total']

            # 3️⃣ Argent remis au ROT (mois en cours)
            total_remis_rot = RecouvrementSuperviseur.objects.filter(
                superviseur=sup,
                date_recouvrement__gte=debut_mois
            ).aggregate(
                total=Coalesce(Sum('montant'), Decimal('0.00'))
            )['total']

            # 4️⃣ Argent encore détenu ce mois
            argent_chez_superviseur = (
                total_recouvre_agents
                + ventes_superviseur
                - total_remis_rot
            )

            # 5️⃣ Stock restant (hors notion temporelle)
            stock_restant = AffectationLotSuperviseur.objects.filter(
                superviseur=sup
            ).aggregate(
                total=Coalesce(Sum('quantite_restante'), Decimal('0.00'))
            )['total']

            data.append({
                'superviseur': sup,
                'stock_restant': stock_restant,

                # flux cash mensuel
                'recouvre_agents_mois': total_recouvre_agents,
                'ventes_superviseur_mois': ventes_superviseur,
                'total_remis_rot_mois': total_remis_rot,

                # KPI clé
                'reste_a_remettre_mois': max(argent_chez_superviseur, Decimal('0.00')),
            })

        return data

    @staticmethod
    def get_cash_superviseur_post_cloture(superviseur):
        """
        Cash réel du superviseur depuis la dernière clôture validée
        """
    
        cloture = (
            ClotureMensuelle.objects
            .filter(superviseur=superviseur, est_cloture=True)
            .order_by('-date_fin_periode')
            .first()
        )
    
        date_ref = cloture.date_fin_periode if cloture else None
    
        # 1️⃣ Recouvrements agents
        recouvrements = Recouvrement.objects.filter(
            superviseur=superviseur
        )
        if date_ref:
            recouvrements = recouvrements.filter(
                date_recouvrement__date__gt=date_ref
            )
    
        total_recouvre = recouvrements.aggregate(
            total=Coalesce(Sum('montant_recouvre'), Decimal('0.00'))
        )['total']
    
        # 2️⃣ Ventes superviseur
        ventes = Vente.objects.filter(
            agent=superviseur,
            est_supprime=False
        )
        if date_ref:
            ventes = ventes.filter(
                date_vente__date__gt=date_ref
            )
    
        total_ventes = ventes.aggregate(
            total=Coalesce(
                Sum(F('quantite') * F('prix_vente_unitaire')),
                Decimal('0.00')
            )
        )['total']
    
        # 3️⃣ Remises ROT
        remises = RecouvrementSuperviseur.objects.filter(
            superviseur=superviseur
        )
        if date_ref:
            remises = remises.filter(
                date_recouvrement__date__gt=date_ref
            )
    
        total_remis = remises.aggregate(
            total=Coalesce(Sum('montant'), Decimal('0.00'))
        )['total']
    
        cash_disponible = total_recouvre + total_ventes
        cash_restant = max(cash_disponible - total_remis, Decimal('0.00'))
    
        return {
            'date_reference': date_ref,
            'total_recouvre': total_recouvre,
            'total_ventes': total_ventes,
            'total_remis': total_remis,
            'cash_disponible': cash_disponible,
            'cash_restant': cash_restant,
        }
    
    # =====================================================
    # 3️⃣ ALERTES ROT
    # =====================================================
    @staticmethod
    def get_alertes():
        alertes = []
        seuil = Decimal('50000')

        for ligne in RotDashboardService.get_suivi_superviseurs():
            if ligne['reste_a_remettre_mois'] > seuil:
                alertes.append({
                    'type': 'finance',
                    'niveau': 'danger',
                    'message': (
                        f"{ligne['superviseur'].full_name} "
                        f"doit encore {ligne['reste_a_remettre_mois']} FCFA"
                    )
                })

        return alertes

    @staticmethod
    def get_tableau_fournisseurs():
        """
        Vue économique Fournisseur
        Pilotée par la Direction – consultable par le ROT
        """

        data = []

        fournisseurs = Fournisseur.objects.all()

        for f in fournisseurs:
            # ---------------------------
            # Lots livrés
            # ---------------------------
            lots = LotEntrepot.objects.filter(fournisseur=f)

            qte_livree = lots.aggregate(
                total=Coalesce(Sum('quantite_initiale'), Decimal('0'))
            )['total']

            dette_contractuelle = lots.aggregate(
                total=Coalesce(
                    Sum(
                        F('quantite_initiale') * F('prix_achat_unitaire'),
                        output_field=DecimalField(max_digits=15, decimal_places=2)
                    ),
                    Decimal('0')
                )
            )['total']

            # ---------------------------
            # Quantité vendue
            # ---------------------------
            ventes = Vente.objects.filter(
                detail_distribution__lot__fournisseur=f
            )

            qte_vendue = ventes.aggregate(
                total=Coalesce(Sum('quantite'), Decimal('0'))
            )['total']

            # ---------------------------
            # Dette consommée (marge)
            # ---------------------------
            dette_consommee = ventes.aggregate(
                total=Coalesce(
                    Sum(
                        F('quantite') *
                        (F('prix_vente_unitaire') - F('detail_distribution__lot__prix_achat_unitaire')),
                        output_field=DecimalField(max_digits=15, decimal_places=2)
                    ),
                    Decimal('0')
                )
            )['total']

            # ---------------------------
            # Paiements
            # ---------------------------
            paye = PaiementFournisseur.objects.filter(
                fournisseur=f,
                est_supprime=False
            ).aggregate(
                total=Coalesce(Sum('montant'), Decimal('0'))
            )['total']

            reste = dette_contractuelle - paye

            data.append({
                'fournisseur': f,
                'qte_livree': qte_livree,
                'qte_vendue': qte_vendue,
                'dette_contractuelle': dette_contractuelle,
                'dette_consommee': dette_consommee,
                'paye': paye,
                'reste': reste,
            })

        return data

    # =====================================================
    # 4️⃣ BUILD DASHBOARD
    # =====================================================
    @staticmethod
    def build_dashboard(rot):
        return {
            'kpis': RotDashboardService.get_kpis(rot),
            'stock_entrepot': RotDashboardService.get_stock_entrepot(),
            'stock_critique': RotDashboardService.get_stock_critique(),

            'suivi_superviseurs': RotDashboardService.get_suivi_superviseurs(),
            'fournisseurs': RotDashboardService.get_tableau_fournisseurs(),
            'fournisseurs_rot': RotFournisseurService.get_suivi_fournisseurs_rot(),
            'alertes': RotDashboardService.get_alertes(),
        }
