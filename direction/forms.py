from django import forms
from django.core.exceptions import ValidationError
from datetime import date

class CalculSalaireForm(forms.Form):
    """Formulaire pour calculer les salaires sur une période"""
    date_debut = forms.DateField(
        label="Date de début",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=True
    )
    
    date_fin = forms.DateField(
        label="Date de fin",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=True
    )
    
    agent = forms.ModelChoiceField(
        queryset=None,
        label="Agent (optionnel - laisser vide pour tous)",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Tous les agents"
    )
    
    inclure_stagiaires = forms.BooleanField(
        label="Inclure les stagiaires",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        from core.models import Agent
        super().__init__(*args, **kwargs)
        # Filtrer les agents actifs (sauf direction)
        self.fields['agent'].queryset = Agent.objects.filter(
            est_actif=True,
            type_agent__in=['terrain', 'entrepot']
        ).order_by('user__last_name')
    
    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')
        
        if date_debut and date_fin:
            if date_debut > date_fin:
                raise ValidationError("La date de début doit être antérieure à la date de fin.")
            
            # Limiter à 3 mois maximum
            delta = date_fin - date_debut
            if delta.days > 90:
                raise ValidationError("La période ne peut pas dépasser 3 mois.")
        
        return cleaned_data


class ExportSalaireForm(forms.Form):
    """Formulaire pour exporter les salaires"""
    format = forms.ChoiceField(
        choices=[
            ('excel', 'Excel (.xlsx)'),
            ('pdf', 'PDF'),
            ('csv', 'CSV')
        ],
        initial='excel',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label="Format d'export"
    )
    
    inclure_details = forms.BooleanField(
        label="Inclure le détail des ventes",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


# Types d'agents rattachables à un superviseur (aligné sur la commande
# management `affecter_superviseurs`).
TYPES_AGENTS_GERES = ('terrain', 'agent_gros', 'stagiaire')


class ReaffectationAgentsForm(forms.Form):
    """
    Transfert d'un lot d'agents d'un superviseur vers un autre.

    Le queryset des agents est restreint dynamiquement au portefeuille du
    superviseur source (voir ``__init__``) pour qu'on ne puisse pas transférer
    un agent qui n'appartient pas à la source affichée.
    """

    superviseur_source = forms.ModelChoiceField(
        queryset=None,
        label="Superviseur source",
        empty_label="— Choisir —",
    )
    superviseur_cible = forms.ModelChoiceField(
        queryset=None,
        label="Superviseur cible",
        empty_label="— Choisir —",
    )
    agents = forms.ModelMultipleChoiceField(
        queryset=None,
        label="Agents à transférer",
        widget=forms.CheckboxSelectMultiple,
    )
    motif = forms.CharField(
        label="Motif du transfert",
        required=False,
        widget=forms.Textarea(attrs={'rows': 2}),
    )

    def __init__(self, *args, **kwargs):
        source = kwargs.pop('source', None)
        super().__init__(*args, **kwargs)

        from core.models import Agent

        superviseurs = Agent.objects.filter(
            type_agent='entrepot'
        ).select_related('user').order_by('user__first_name', 'user__username')

        self.fields['superviseur_source'].queryset = superviseurs
        self.fields['superviseur_cible'].queryset = superviseurs

        # Le champ "agents" n'accepte que le portefeuille de la source.
        if source is not None:
            portefeuille = Agent.objects.filter(
                superviseur=source,
                type_agent__in=TYPES_AGENTS_GERES,
            ).select_related('user').order_by('user__first_name', 'user__username')
        else:
            portefeuille = Agent.objects.none()
        self.fields['agents'].queryset = portefeuille

    def clean(self):
        cleaned = super().clean()
        source = cleaned.get('superviseur_source')
        cible = cleaned.get('superviseur_cible')
        agents = cleaned.get('agents')

        if source and cible and source == cible:
            raise ValidationError(
                "Le superviseur cible doit être différent du superviseur source."
            )

        if source and agents:
            hors_portefeuille = [
                a for a in agents if a.superviseur_id != source.id
            ]
            if hors_portefeuille:
                noms = ", ".join(a.full_name for a in hors_portefeuille)
                raise ValidationError(
                    f"Ces agents ne sont plus rattachés à {source.full_name} : {noms}."
                )

        return cleaned


# ============================================================================
# CORRECTIONS ADMINISTRATIVES (sprint-13, accès restreint : mdmaiga)
# ============================================================================


_INPUT_CLASS = 'input input-bordered input-sm w-full'
_SELECT_CLASS = 'select select-bordered select-sm w-full'
_TEXTAREA_CLASS = 'textarea textarea-bordered textarea-sm w-full'


class CorrectionLotForm(forms.Form):
    """Correction d'un LotEntrepot à la réception — quantité, prix,
    fournisseur, date. Le motif est facultatif (décision mdmaiga,
    2026-09-15) : une correction reste tracée (qui/quand/avant/après) même
    sans commentaire.
    """

    quantite_initiale = forms.DecimalField(
        label="Quantité initiale",
        min_value=0.01,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': _INPUT_CLASS, 'step': '0.01'}),
    )
    prix_achat_unitaire = forms.DecimalField(
        label="Prix d'achat unitaire",
        min_value=0.01,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': _INPUT_CLASS, 'step': '0.01'}),
    )
    fournisseur = forms.ModelChoiceField(
        queryset=None,
        label="Fournisseur",
        required=False,
        empty_label="(inchangé)",
        widget=forms.Select(attrs={'class': _SELECT_CLASS}),
    )
    date_reception = forms.DateField(
        label="Date de réception",
        widget=forms.DateInput(attrs={'type': 'date', 'class': _INPUT_CLASS}),
        required=False,
    )
    motif = forms.CharField(
        label="Motif de la correction (facultatif)",
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': _TEXTAREA_CLASS}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        from core.models import Fournisseur

        self.fields['fournisseur'].queryset = Fournisseur.objects.order_by('nom')

    def clean(self):
        cleaned = super().clean()
        if not any(
            cleaned.get(champ) is not None
            for champ in ('quantite_initiale', 'prix_achat_unitaire', 'fournisseur', 'date_reception')
        ):
            raise ValidationError(
                "Indiquez au moins une quantité, un prix, un fournisseur ou une date corrigés."
            )
        return cleaned


class CorrectionDistributionForm(forms.Form):
    """Correction d'une distribution déjà enregistrée — superviseur, agent,
    produit/lot distribué, quantité, date.

    ``superviseur`` est toujours pré-sélectionné à la valeur courante par la
    vue (``initial``), jamais vide — le champ ``agent_terrain`` en dépend
    directement : sa liste ne contient que les agents de ce superviseur, et
    se recharge par AJAX (``/marchandise/ajax/agents-par-superviseur/``)
    dès que ``superviseur`` change côté client, pour ne jamais laisser
    afficher un agent incohérent avec le superviseur affiché. Même logique
    pour ``produit``/``lot`` (``/agents/ajax/lots-par-produit/``) : le lot
    n'est jamais proposé sans son produit.

    Le motif est facultatif (décision mdmaiga, 2026-09-15).
    """

    superviseur = forms.ModelChoiceField(
        queryset=None,
        label="Superviseur",
        widget=forms.Select(attrs={'class': _SELECT_CLASS}),
    )
    agent_terrain = forms.ModelChoiceField(
        queryset=None,
        label="Agent destinataire",
        widget=forms.Select(attrs={'class': _SELECT_CLASS}),
    )
    produit = forms.ModelChoiceField(
        queryset=None,
        label="Produit",
        required=False,
        widget=forms.Select(attrs={'class': _SELECT_CLASS}),
    )
    lot = forms.ModelChoiceField(
        queryset=None,
        label="Lot",
        required=False,
        widget=forms.Select(attrs={'class': _SELECT_CLASS}),
    )
    quantite = forms.DecimalField(
        label="Quantité distribuée",
        min_value=0.01,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': _INPUT_CLASS, 'step': '0.01'}),
    )
    date_distribution = forms.DateField(
        label="Date de la distribution",
        widget=forms.DateInput(attrs={'type': 'date', 'class': _INPUT_CLASS}),
        required=False,
    )
    motif = forms.CharField(
        label="Motif de la correction (facultatif)",
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': _TEXTAREA_CLASS}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        from core.models import Agent, LotEntrepot, Produit

        self.fields['superviseur'].queryset = Agent.objects.filter(
            type_agent='entrepot'
        ).select_related('user').order_by('user__first_name', 'user__username')
        self.fields['produit'].queryset = Produit.objects.order_by('nom')

        # agent_terrain/lot : vides au GET (sauf préremplissage explicite par
        # la vue via `initial`), peuplés côté client par AJAX au changement
        # de superviseur/produit ; en POST, filtrés sur le seul ID soumis
        # pour valider sans bloquer (même pattern que
        # marchandise.AffectationSuperviseurForm).
        agent_id = self.data.get('agent_terrain') if self.is_bound else self.initial.get('agent_terrain')
        if agent_id:
            self.fields['agent_terrain'].queryset = Agent.objects.filter(pk=agent_id)
        else:
            self.fields['agent_terrain'].queryset = Agent.objects.none()

        lot_id = self.data.get('lot') if self.is_bound else self.initial.get('lot')
        if lot_id:
            self.fields['lot'].queryset = LotEntrepot.objects.filter(pk=lot_id)
        else:
            self.fields['lot'].queryset = LotEntrepot.objects.none()

    def clean(self):
        cleaned = super().clean()
        superviseur = cleaned.get('superviseur')
        agent_terrain = cleaned.get('agent_terrain')
        if superviseur and agent_terrain and agent_terrain.superviseur_id != superviseur.pk:
            raise ValidationError(
                f"{agent_terrain.full_name} n'est pas rattaché au superviseur "
                f"{superviseur.full_name}."
            )
        return cleaned


class CorrectionVenteForm(forms.Form):
    """Correction d'une Vente déjà enregistrée — prix, quantité et/ou date."""

    prix_vente_unitaire = forms.DecimalField(
        label="Prix de vente unitaire",
        min_value=0.01,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': _INPUT_CLASS, 'step': '0.01'}),
    )
    quantite = forms.DecimalField(
        label="Quantité vendue",
        min_value=0.01,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': _INPUT_CLASS, 'step': '0.01'}),
    )
    date_vente = forms.DateField(
        label="Date de la vente",
        widget=forms.DateInput(attrs={'type': 'date', 'class': _INPUT_CLASS}),
        required=False,
    )
    motif = forms.CharField(
        label="Motif de la correction (facultatif)",
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': _TEXTAREA_CLASS}),
    )

    def clean(self):
        cleaned = super().clean()
        if not any(
            cleaned.get(champ) is not None
            for champ in ('prix_vente_unitaire', 'quantite', 'date_vente')
        ):
            raise ValidationError("Indiquez au moins un prix, une quantité ou une date corrigés.")

        return cleaned