# core/services/superviseur_analysis_service.py

from finance.services import lister_soldes_superviseurs


class SuperviseurAnalysisService:
    """
    Service DIRECTIONNEL — situation financière superviseurs.
    Délègue à finance.services (source de vérité unique, décisions n°13/14/15,
    sprint-03). Remplace l'ancien calcul "post-clôture" local (2026-08-03) :
    ClotureMensuelle/solde_cloture n'est plus la référence d'ouverture du solde,
    finance.services.DATE_DEBUT_FINANCE l'est. La situation financière ROT
    (get_rots_finance) est supprimée : dépréciée, faisait doublon avec
    finance.services sans jamais avoir été alignée dessus.
    """

    # =====================================================
    # SUPERVISEURS – FINANCE
    # =====================================================
    @staticmethod
    def get_superviseurs_finance():
        return lister_soldes_superviseurs()
