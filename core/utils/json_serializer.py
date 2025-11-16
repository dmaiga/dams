# core/utils/json_serializer.py
import json
from datetime import datetime, date
from decimal import Decimal
from django.db.models import Model
from django.utils.timezone import is_aware

class JSONEncoder(json.JSONEncoder):
    """
    Encodeur JSON personnalisé qui gère les types Django
    """
    def default(self, obj):
        # Gérer les dates datetime
        if isinstance(obj, datetime):
            return obj.isoformat()
        
        # Gérer les dates date
        elif isinstance(obj, date):
            return obj.isoformat()
        
        # Gérer les Decimal
        elif isinstance(obj, Decimal):
            return float(obj)
        
        # Gérer les modèles Django
        elif isinstance(obj, Model):
            return str(obj)
        
        # Gérer les timezone-aware datetime
        elif is_aware(obj):
            return obj.isoformat()
        
        return super().default(obj)

def safe_json_dumps(data, indent=2):
    """
    Sérialise en JSON en gérant les types Django
    """
    return json.dumps(data, indent=indent, ensure_ascii=False, cls=JSONEncoder)