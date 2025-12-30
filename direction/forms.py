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