from decimal import Decimal

from django.db.models import Sum, F, DecimalField
from django.db.models.functions import Coalesce

from core.models import (
    Agent,
    Vente,
    RecouvrementSuperviseur,
    VersementBancaire,
    Depense,
    ClotureMensuelle,
    LotEntrepot,
    AffectationLotSuperviseur,
    Fournisseur,
      PaiementFournisseur,
)

from django.db.models import ExpressionWrapper

def get_date_debut_rot():
    """
    Date à partir de laquelle le ROT devient opérationnel.
    """
    cloture = (
        ClotureMensuelle.objects
        .filter(est_cloture=True)
        .order_by('-date_fin_periode')
        .first()
    )
    return cloture.date_fin_periode if cloture else None



class RotDashboardService:

    SEUIL_STOCK_FAIBLE = 10

    @staticmethod
    def get_stock_entrepot():
        produits = (
            LotEntrepot.objects
            .values('produit__nom')
            .annotate(
                quantite_restante=Coalesce(Sum('quantite_restante'), Decimal('0'))
            )
            .order_by('produit__nom')
        )

        # Calculer la valeur du stock pour chaque produit
        for produit in produits:
            valeur_stock = (
                LotEntrepot.objects
                .filter(produit__nom=produit['produit__nom'])
                .aggregate(
                    valeur=Coalesce(
                        Sum(
                            F('quantite_restante') * F('prix_achat_unitaire'),
                            output_field=DecimalField(max_digits=15, decimal_places=2)
                        ),
                        Decimal('0'),
                        output_field=DecimalField(max_digits=15, decimal_places=2)
                    )
                )['valeur']
            )
            produit['valeur_stock'] = valeur_stock

        return {
            'produits': produits,
            'seuil_faible': RotDashboardService.SEUIL_STOCK_FAIBLE
        }

    # =====================================================
    # 1️⃣ KPIs GLOBAUX ROT
    # =====================================================
    @staticmethod
    def get_kpis():
        date_min = get_date_debut_rot()

        recouvre_qs = RecouvrementSuperviseur.objects.all()
        versement_qs = VersementBancaire.objects.all()
        depense_qs = Depense.objects.all()

        if date_min:
            recouvre_qs = recouvre_qs.filter(date_recouvrement__date__gt=date_min)
            versement_qs = versement_qs.filter(date_versement_reelle__date__gt=date_min)
            depense_qs = depense_qs.filter(date_depense__date__gt=date_min)

        total_recupere = recouvre_qs.aggregate(
            total=Coalesce(Sum('montant'), Decimal('0'))
        )['total']

        versements = versement_qs.aggregate(
            vente=Coalesce(Sum('montant_vente'), Decimal('0')),
            hors_vente=Coalesce(Sum('montant_hors_vente'), Decimal('0')),
        )
        total_verse = versements['vente'] + versements['hors_vente']

        total_depenses = depense_qs.aggregate(
            total=Coalesce(Sum('montant'), Decimal('0'))
        )['total']

        return {
            'total_recupere_rot': total_recupere,
            'total_verse_banque': total_verse,
            'total_depenses': total_depenses,
            'solde_rot': total_recupere - total_verse - total_depenses,
        }


    # =====================================================
    # 2️⃣ SUIVI FINANCIER DES SUPERVISEURS (POST-CLÔTURE)
    # =====================================================
    @staticmethod
    def get_suivi_superviseurs():
        data = []
    
        superviseurs = Agent.objects.filter(
            type_agent='entrepot',
            est_actif=True
        )
    
        for sup in superviseurs:
            date_min = get_date_debut_rot()
    
            # 🔹 VENTES POST-CLÔTURE
            ventes_qs = Vente.objects.filter(agent__superviseur=sup)
            remises_qs = RecouvrementSuperviseur.objects.filter(superviseur=sup)
    
            if date_min:
                ventes_qs = ventes_qs.filter(date_vente__date__gt=date_min)
                remises_qs = remises_qs.filter(date_recouvrement__date__gt=date_min)
    
            total_ventes = ventes_qs.aggregate(
                total=Coalesce(
                    Sum(
                        F('quantite') * F('prix_vente_unitaire'),
                        output_field=DecimalField(max_digits=15, decimal_places=2)
                    ),
                    Decimal('0')
                )
            )['total']
    
            total_remis = remises_qs.aggregate(
                total=Coalesce(Sum('montant'), Decimal('0'))
            )['total']
    
            # 🔹 STOCK RESTANT CHEZ LE SUPERVISEUR
            stock_restant = AffectationLotSuperviseur.objects.filter(
                superviseur=sup
            ).aggregate(
                total=Coalesce(Sum('quantite_restante'), Decimal('0'))
            )['total']
    
            data.append({
                'superviseur': sup,
                'quantite_restante': stock_restant,
                'total_ventes_agents': total_ventes,
                'total_remis_rot': total_remis,
                'reste_a_remettre': total_ventes - total_remis,
            })
    
        return data

    # =====================================================
    # 3️⃣ ALERTES ROT
    # =====================================================
    @staticmethod
    def get_alertes():
        alertes = []
        seuil = Decimal('50000')

        for ligne in RotDashboardService.get_suivi_superviseurs():
            if ligne['reste_a_remettre'] > seuil:
                alertes.append({
                    'type': 'finance',
                    'niveau': 'danger',
                    'message': (
                        f"{ligne['superviseur'].full_name} "
                        f"doit encore {ligne['reste_a_remettre']} FCFA"
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
    def build_dashboard():
        return {
            'kpis': RotDashboardService.get_kpis(),
            'stock_entrepot': RotDashboardService.get_stock_entrepot(),
            'suivi_superviseurs': RotDashboardService.get_suivi_superviseurs(),
            'fournisseurs': RotDashboardService.get_tableau_fournisseurs(),
            'alertes': RotDashboardService.get_alertes(),
        }
