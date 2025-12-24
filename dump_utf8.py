import os
import django

# 🔹 Charger Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dams.settings")  # ⚠️ adapte si besoin
django.setup()

from django.core.management import call_command

print("📦 Export des données en UTF-8...")

with open("data.json", "w", encoding="utf-8") as f:
    call_command(
        "dumpdata",
        exclude=["auth.permission", "contenttypes"],
        natural_foreign=True,
        natural_primary=True,
        stdout=f
    )

print("✅ Dump terminé : data.json créé avec encodage UTF-8")
