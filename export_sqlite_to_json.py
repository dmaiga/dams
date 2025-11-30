import json
import subprocess

def export_dump():
    print("📤 Exportation des données SQLite...")

    # Commande dumpdata
    cmd = [
        "python", "manage.py", "dumpdata",
        "--exclude", "auth.permission",
        "--exclude", "contenttypes",
        "--exclude", "admin.logentry",
        "--exclude", "sessions"
    ]

    # Exécuter et capturer stdout
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    raw_output = proc.stdout.read()

    print("✔ Données capturées depuis dumpdata")

    # Decode UTF-8 strict (ignore BOM si présent)
    text = raw_output.decode("utf-8", errors="ignore")

    print("✔ JSON décodé sans erreurs")

    # Charger et re-sauvegarder proprement
    data = json.loads(text)
    with open("dump_clean.json", "w", encoding="utf-8") as f:
        json.dump(data, f)

    print("🎉 Dump nettoyé et sauvegardé → dump_clean.json")

if __name__ == "__main__":
    export_dump()
