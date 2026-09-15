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
    """Correction d'un LotEntrepot à la réception — quantité, prix, date."""

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
    date_reception = forms.DateField(
        label="Date de réception",
        widget=forms.DateInput(attrs={'type': 'date', 'class': _INPUT_CLASS}),
        required=False,
    )
    motif = forms.CharField(
        label="Motif de la correction",
        widget=forms.Textarea(attrs={'rows': 2, 'class': _TEXTAREA_CLASS}),
    )

    def clean(self):
        cleaned = super().clean()
        if not any(
            cleaned.get(champ) is not None
            for champ in ('quantite_initiale', 'prix_achat_unitaire', 'date_reception')
        ):
            raise ValidationError(
                "Indiquez au moins une quantité, un prix ou une date corrigés."
            )
        return cleaned


class CorrectionDistributionForm(forms.Form):
    """Correction d'une distribution déjà enregistrée — agent, superviseur,
    quantité. Même pattern AJAX que ``marchandise.AffectationSuperviseurForm`` :
    ``agent_terrain`` est vide au GET, peuplé par changement de superviseur
    côté client, puis filtré sur l'ID soumis en POST pour valider sans bloquer.
    """

    superviseur = forms.ModelChoiceField(
        queryset=None,
        label="Superviseur",
        required=False,
        empty_label="(inchangé)",
        widget=forms.Select(attrs={'class': _SELECT_CLASS}),
    )
    agent_terrain = forms.ModelChoiceField(
        queryset=None,
        label="Agent destinataire",
        required=False,
        empty_label="(inchangé)",
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
        label="Motif de la correction",
        widget=forms.Textarea(attrs={'rows': 2, 'class': _TEXTAREA_CLASS}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        from core.models import Agent

        self.fields['superviseur'].queryset = Agent.objects.filter(
            type_agent='entrepot'
        ).select_related('user').order_by('user__first_name', 'user__username')

        agent_id = self.data.get('agent_terrain') if self.is_bound else None
        if agent_id:
            self.fields['agent_terrain'].queryset = Agent.objects.filter(pk=agent_id)
        else:
            self.fields['agent_terrain'].queryset = Agent.objects.none()

    def clean(self):
        cleaned = super().clean()
        if not any(
            cleaned.get(champ) is not None
            for champ in ('superviseur', 'agent_terrain', 'quantite', 'date_distribution')
        ):
            raise ValidationError(
                "Indiquez au moins un agent, un superviseur, une quantité ou une date corrigés."
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
        label="Motif de la correction",
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