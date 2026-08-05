from decimal import Decimal

from django import forms
from tinymce.widgets import TinyMCE

from core.models import Agent, RecuVersement, VersementBancaire

# Réutilisés tels quels — aucune restriction de type_agent au niveau modèle/form :
from core.forms import DepenseForm  # noqa: F401
from agents.forms import RecouvrementSuperviseurForm  # noqa: F401


class EngagementChampForm(forms.Form):
    """
    Création d'une avance de trésorerie ou d'une dépense pour le compte du
    champ. Formulaire simple (pas un ModelForm) : la création réelle passe
    par finance.services.creer_engagement_champ, qui synchronise d'abord
    avec dams_agro avant d'écrire la Depense correspondante.
    """
    NATURE_CHOICES = (
        ('AVANCE_CHAMP', 'Avance de trésorerie — envoyer du cash au champ'),
        ('DEPENSE_CHAMP', 'Dépense pour le compte du champ — vous payez directement'),
    )

    nature = forms.ChoiceField(
        choices=NATURE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Nature de l'engagement",
    )
    montant = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        label="Montant",
    )
    commentaire = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        label="Commentaire",
        help_text="Ex : achat pièces détachées, transport, avance carburant...",
    )


class RemboursementChampForm(forms.Form):
    """Remboursement (partiel ou total) d'une avance/dépense champ."""

    montant = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        label="Montant remboursé",
    )


class VersementBancaireForm(forms.ModelForm):
    """
    Version finance de VersementForm (core.forms) : pas de champ `superviseur`
    — c'est un champ historique dupliquant `effectue_par` (même rôle : qui a
    effectué l'action), pas une attribution à un superviseur source. Une fois
    la recette d'un superviseur remise (RecouvrementSuperviseur), l'argent est
    mutualisé : le versement bancaire est un événement de la caisse globale,
    pas d'un superviseur en particulier (voir sprint-03, décision n°13).
    """

    recus = forms.FileField(
        required=False,
        label="Reçu(s) de versement",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx',
        }),
        help_text="Maintenez Ctrl pour sélectionner plusieurs fichiers"
    )

    recus_description = forms.CharField(
        required=False,
        label="Description des reçus",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = VersementBancaire
        fields = [
            'montant_vente',
            'montant_hors_vente',
            'description',
            'date_versement_reelle',
        ]
        widgets = {
            'montant_vente': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'montant_hors_vente': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'description': TinyMCE(attrs={'rows': 2, 'class': 'form-control'}),
            'date_versement_reelle': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
            }),
        }
        help_texts = {
            'montant_hors_vente': "N'impacte pas le solde recette (traçabilité uniquement).",
        }

    def save(self, effectue_par, commit=True):
        if effectue_par is None or not (effectue_par.est_rot or effectue_par.est_direction):
            raise ValueError("Le versement doit être effectué par un ROT ou la Direction")

        versement = super().save(commit=False)
        versement.effectue_par = effectue_par

        if commit:
            versement.save()

            recus_files = self.files.getlist('recus')
            description = (self.cleaned_data.get('recus_description') or "").strip()
            for recu_file in recus_files:
                RecuVersement.objects.create(
                    versement=versement,
                    fichier=recu_file,
                    description=description or f"Reçu pour versement {versement.id}"
                )

        return versement


class DepenseFinanceForm(DepenseForm):
    """
    Étend DepenseForm (core.forms) : mdmaiga peut saisir la dépense en son nom
    ou au nom d'un agent habilité (ROT / superviseur avec peut_faire_depense).
    """
    agent_cible = forms.ModelChoiceField(
        queryset=Agent.objects.filter(
            type_agent__in=['entrepot', 'rot', 'direction'], est_actif=True
        ).select_related('user'),
        required=False,
        label="Effectuée par (si différent de vous)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def save(self, agent, commit=True):
        cible = self.cleaned_data.get('agent_cible') or agent
        return super().save(agent=cible, commit=commit)


class LigneRecouvrementVersementForm(forms.Form):
    """
    Une ligne du formset groupé : recouvrement + versement + reçu pour UN
    superviseur, en une seule soumission. Tous les champs (sauf superviseur)
    sont optionnels — un superviseur sans recette laisse sa ligne vide et
    n'est simplement pas traité (voir recouvrement_versement_groupe).
    """
    superviseur = forms.ModelChoiceField(
        queryset=Agent.objects.filter(type_agent='entrepot', est_actif=True),
        widget=forms.HiddenInput,
    )
    montant = forms.DecimalField(
        max_digits=12, decimal_places=2, required=False, min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'input input-bordered input-sm w-32',
            'step': '0.01',
        })
    )
    montant_hors_vente = forms.DecimalField(
        max_digits=12, decimal_places=2, required=False, min_value=0,
        label="Apport (hors vente)",
        widget=forms.NumberInput(attrs={
            'class': 'input input-bordered input-sm w-32',
            'step': '0.01',
        })
    )
    recu = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'file-input file-input-bordered file-input-sm w-full max-w-xs',
            'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx',
        })
    )


RecouvrementVersementFormSet = forms.formset_factory(LigneRecouvrementVersementForm, extra=0)
