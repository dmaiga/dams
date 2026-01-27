from multiprocessing import context
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from core.models import Salaire
from paie.services.salaire_liste_service import SalaireListeService
from paie.services.salaire_generation_service import SalaireGenerationService



class SalaireLectureView(LoginRequiredMixin, TemplateView):
    template_name = "paie/salaire_liste.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # ----------------------------
        # PÉRIODE
        # ----------------------------
        periode = self.request.GET.get("periode", "mensuel")
        today = timezone.now().date()

        if periode == "custom":
            date_debut = self.request.GET.get("date_debut")
            date_fin = self.request.GET.get("date_fin")

            if date_debut and date_fin:
                date_debut = datetime.strptime(date_debut, "%Y-%m-%d").date()
                date_fin = datetime.strptime(date_fin, "%Y-%m-%d").date()
            else:
                date_debut = today.replace(day=1)
                date_fin = today
        else:
            date_debut = today.replace(day=1)
            date_fin = today

        # ----------------------------
        # FILTRE TYPE AGENT
        # ----------------------------
        current_type_agent = self.request.GET.get("type_agent", "")

        # ----------------------------
        # SERVICE
        # ----------------------------
        result = SalaireListeService.get_salaires(
            date_debut=date_debut,
            date_fin=date_fin,
            type_agent_filter=current_type_agent
        )

        salaires_qs = Salaire.objects.filter(
            date_debut=date_debut,
            date_fin=date_fin
        )

        periode_generee = salaires_qs.exists()
        periode_validee = (
            periode_generee and
            not salaires_qs.filter(valide=False).exists()
        )

        # ----------------------------
        # CONTEXT FINAL
        # ----------------------------
        context.update({
            "salaires_mamy": result["mamies"],
            "salaires_gros": result["gros"],
            "salaires_superviseur": result["superviseurs"],
        
            # 👩‍🌾 Mamies
            "total_mamy_kilo": result["total_mamy_kilo"],
            "total_mamy_salaire_base": result["total_mamy_salaire_base"],
            "total_mamy_incentive": result["total_mamy_incentive"],
            "total_mamy_general": result["total_mamy_general"],
        
            # 📦 Agents gros
            "total_gros_cartons": result["total_gros_cartons"],
            "total_gros_incentive": result["total_gros_incentive"],
            "total_gros_general": result["total_gros_general"],
        
            # 🏢 Superviseurs
            "total_sup_kilo_mamies": result["total_sup_kilo_mamies"],
            "total_sup_salaire_base": result["total_sup_salaire_base"],
            "total_sup_dotation": result["total_sup_dotation"],
            "total_sup_bonus": result["total_sup_bonus"],
            "total_sup_general": result["total_sup_general"],
        
            "total_global": result["total_global"],
        })
        

        return context


class SalaireGenerationView(LoginRequiredMixin, View):
    template_name = "paie/salaire_generation.html"

    def get(self, request):
        today = timezone.now().date()
        date_debut = today.replace(day=1)
        date_fin = today

        # Vérifier s'il y a déjà des salaires (validés ou non)
        salaires_existants = Salaire.objects.filter(
            date_debut=date_debut,
            date_fin=date_fin
        )
        
        deja_genere = salaires_existants.exists()
        deja_valide = salaires_existants.filter(valide=True).exists()

        return render(request, self.template_name, {
            "date_debut": date_debut,
            "date_fin": date_fin,
            "deja_genere": deja_genere,
            "deja_valide": deja_valide,
        })

    def post(self, request):
        try:
            date_debut = datetime.strptime(
                request.POST.get("date_debut"), "%Y-%m-%d"
            ).date()
            date_fin = datetime.strptime(
                request.POST.get("date_fin"), "%Y-%m-%d"
            ).date()

            # Vérifier s'il y a des salaires déjà validés
            salaires_valides = Salaire.objects.filter(
                date_debut=date_debut,
                date_fin=date_fin,
                valide=True
            )
            
            if salaires_valides.exists():
                messages.warning(
                    request,
                    f"{salaires_valides.count()} salaires déjà validés pour cette période. "
                    "Impossible de regénérer."
                )
                return redirect("salaire_generation")

            # Générer/Mettre à jour
            salaires = SalaireGenerationService.generate(date_debut, date_fin)
            
            messages.success(
                request,
                f"{len(salaires)} salaires générés/mis à jour avec succès."
            )
            return redirect("salaire_lecture")

        except ValueError as e:
            messages.error(request, str(e))

        except Exception as e:
            messages.error(request, f"Erreur: {str(e)}")

        return redirect("salaire_generation")
    
class SalaireValidationView(LoginRequiredMixin, View):
    template_name = "paie/salaire_validation.html"

    def get(self, request):
        date_debut = request.GET.get("date_debut")
        date_fin = request.GET.get("date_fin")

        if not date_debut or not date_fin:
            messages.error(request, "Période invalide.")
            return redirect("salaire_lecture")

        return render(request, self.template_name, {
            "date_debut": date_debut,
            "date_fin": date_fin,
        })

    def post(self, request):
        try:
            date_debut = datetime.strptime(
                request.POST.get("date_debut"), "%Y-%m-%d"
            ).date()
            date_fin = datetime.strptime(
                request.POST.get("date_fin"), "%Y-%m-%d"
            ).date()

            qs = Salaire.objects.filter(
                date_debut=date_debut,
                date_fin=date_fin,
                valide=False
            )

            if not qs.exists():
                messages.warning(request, "Aucun salaire à valider.")
                return redirect("salaire_lecture")

            qs.update(valide=True)

            messages.success(
                request,
                "Salaires validés avec succès. Ils sont maintenant figés."
            )

        except Exception as e:
            messages.error(request, f"Erreur : {e}")

        return redirect("salaire_lecture")
