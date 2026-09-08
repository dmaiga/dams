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