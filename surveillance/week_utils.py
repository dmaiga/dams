import re
from datetime import date, timedelta, datetime

def debut_semaine(d: date) -> date:
    """Retourne le lundi de la semaine contenant d."""
    return d - timedelta(days=d.weekday())

def fin_semaine(d: date) -> date:
    """Retourne le dimanche de la semaine contenant d."""
    return debut_semaine(d) + timedelta(days=6)

def semaine_precedente(debut: date) -> tuple[date, date]:
    """Retourne (lundi, dimanche) de la semaine précédant 'debut'."""
    prec = debut - timedelta(weeks=1)
    return prec, prec + timedelta(days=6)

def parse_semaine(raw: str | None) -> date:
    """
    Reçoit la valeur du <input type="week"> (ex: "2026-W25").
    Retourne le lundi correspondant.
    Retourne le lundi de la semaine courante si raw est absent, invalide ou dans le futur.
    """
    today = date.today()
    current_monday = today - timedelta(days=today.weekday())
    
    if raw:
        match = re.match(r'^(\d{4})-W(\d{1,2})$', raw)
        if match:
            try:
                year = int(match.group(1))
                week = int(match.group(2))
                parsed_date = datetime.strptime(f"{year}-W{week}-1", "%G-W%V-%u").date()
                # Empêche la sélection d'une semaine future
                if parsed_date > current_monday:
                    return current_monday
                return parsed_date
            except ValueError:
                pass
    return current_monday

def date_to_week_string(d: date) -> str:
    """Retourne une chaîne au format 'YYYY-Www' pour la date d."""
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"
