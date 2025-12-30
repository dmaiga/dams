from datetime import date, datetime
from decimal import Decimal
from django.db.models import Sum, Q
from django.utils import timezone
from core.models import Vente, Recouvrement, Agent
from django.contrib.auth import get_user_model

User = get_user_model()


class SalaireService:
    """Service pour calculer les salaires des agents"""
    
    # Conversion produit → carton
    CONVERSION_CARTON = {
        "Oignons": Decimal("25"),        # 25 kg = 1 carton
        "Ail": Decimal("10"),            # 10 kg = 1 carton
        "Pomme de terre": Decimal("25"), # 25 kg = 1 carton
        "Poivre": Decimal("1"),          # 1 kg = 1 carton
        # Ajoutez d'autres produits si nécessaire
    }
    
    @classmethod
    def calculer_salaire_agent(cls, agent_id, date_debut, date_fin):
        """Calcule le salaire d'un agent spécifique"""
        # Vérifier que l'agent existe
        try:
            agent = Agent.objects.get(id=agent_id)
        except Agent.DoesNotExist:
            return None
        
        # Calcul du salaire de base
        quantite_totale = cls._calculer_quantite_totale(agent_id, date_debut, date_fin)
        salaire_base = cls._calculer_salaire_base(quantite_totale)
        
        # Calcul de l'incentive
        incentive = cls._calculer_incentive(agent_id, date_debut, date_fin)
        
        # Calcul du salaire total
        salaire_total = salaire_base + incentive
        
        return {
            "agent": agent,
            "quantite_totale": quantite_totale,
            "salaire_base": salaire_base,
            "incentive": incentive,
            "salaire_total": salaire_total,
            "date_debut": date_debut,
            "date_fin": date_fin
        }
    
    @classmethod
    def calculer_salaires_tous_agents(cls, date_debut, date_fin):
        """Calcule les salaires de tous les agents pour une période"""
        # Récupérer tous les agents (sauf direction et stagiaires)
        agents = Agent.objects.filter(
            est_actif=True,
            type_agent__in=['terrain', 'entrepot']
        ).select_related('user')
        
        resultats = []
        totaux = {
            "total_salaire_base": Decimal("0"),
            "total_incentive": Decimal("0"),
            "total_general": Decimal("0"),
            "nombre_agents": 0
        }
        
        for agent in agents:
            resultat_agent = cls.calculer_salaire_agent(agent.id, date_debut, date_fin)
            if resultat_agent:
                resultats.append(resultat_agent)
                
                # Ajouter aux totaux
                totaux["total_salaire_base"] += resultat_agent["salaire_base"]
                totaux["total_incentive"] += resultat_agent["incentive"]
                totaux["total_general"] += resultat_agent["salaire_total"]
                totaux["nombre_agents"] += 1
        
        # Trier par salaire total décroissant
        resultats.sort(key=lambda x: x["salaire_total"], reverse=True)
        
        return {
            "resultats": resultats,
            "totaux": totaux,
            "periode": {
                "debut": date_debut,
                "fin": date_fin
            }
        }
    
    @classmethod
    def _calculer_quantite_totale(cls, agent_id, date_debut, date_fin):
        """Calcule la quantité totale vendue par un agent"""
        quantite = Vente.objects.filter(
            agent_id=agent_id,
            date_vente__date__gte=date_debut,
            date_vente__date__lte=date_fin,
            est_supprime=False
        ).aggregate(total=Sum('quantite'))['total']
        
        return Decimal(quantite or "0")
    
    @classmethod
    def _calculer_salaire_base(cls, quantite_totale):
        """Calcule le salaire de base selon les règles"""
        if quantite_totale > 100:
            return Decimal("50000")
        else:
            return quantite_totale * Decimal("250")
    
    @classmethod
    def _calculer_incentive(cls, agent_id, date_debut, date_fin):
        """Calcule l'incentive d'un agent"""
        recouvrements = Recouvrement.objects.filter(
            agent_id=agent_id,
            bonus_accorde=True,
            date_recouvrement__date__gte=date_debut,
            date_recouvrement__date__lte=date_fin,
            vente__type_vente="detail"
        ).select_related(
            "vente__detail_distribution__lot__produit"
        )
        
        incentive_total = Decimal("0")
        
        for recouvrement in recouvrements:
            produit_nom = recouvrement.vente.detail_distribution.lot.produit.nom
            quantite = Decimal(recouvrement.vente.quantite)
            
            ratio = cls.CONVERSION_CARTON.get(produit_nom)
            if ratio:
                cartons = quantite / ratio
                incentive = cartons * Decimal("100")
                incentive_total += incentive
        
        return incentive_total
    
    @classmethod
    def generer_rapport_excel(cls, date_debut, date_fin):
        """Génère un rapport Excel des salaires"""
        import pandas as pd
        from io import BytesIO
        
        resultats = cls.calculer_salaires_tous_agents(date_debut, date_fin)
        
        # Préparer les données pour Excel
        data = []
        for resultat in resultats["resultats"]:
            data.append({
                "Agent ID": resultat["agent"].id,
                "Nom Complet": resultat["agent"].full_name,
                "Type Agent": resultat["agent"].get_type_agent_display(),
                "Quantité Totale": float(resultat["quantite_totale"]),
                "Salaire Base (FCFA)": float(resultat["salaire_base"]),
                "Incentive (FCFA)": float(resultat["incentive"]),
                "Salaire Total (FCFA)": float(resultat["salaire_total"]),
                "Date Début": date_debut.strftime("%d/%m/%Y"),
                "Date Fin": date_fin.strftime("%d/%m/%Y")
            })
        
        # Créer DataFrame
        df = pd.DataFrame(data)
        
        # Ajouter les totaux
        df_totaux = pd.DataFrame([{
            "Agent ID": "TOTAUX",
            "Nom Complet": "",
            "Type Agent": "",
            "Quantité Totale": "",
            "Salaire Base (FCFA)": float(resultats["totaux"]["total_salaire_base"]),
            "Incentive (FCFA)": float(resultats["totaux"]["total_incentive"]),
            "Salaire Total (FCFA)": float(resultats["totaux"]["total_general"]),
            "Date Début": "",
            "Date Fin": ""
        }])
        
        df = pd.concat([df, df_totaux], ignore_index=True)
        
        # Créer fichier Excel en mémoire
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Salaires', index=False)
            
            # Formater les colonnes
            worksheet = writer.sheets['Salaires']
            for column in ['E', 'F', 'G']:  # Colonnes monétaires
                for cell in worksheet[column]:
                    cell.number_format = '#,##0'
        
        output.seek(0)
        return output