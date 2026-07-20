"""Lance dbt en chargeant le .env racine du projet dams (variables DBT_POSTGRES_*)."""
import os
import subprocess
import sys

from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, "..", "..", ".env"))
os.environ.setdefault("DBT_PROFILES_DIR", HERE)

dbt_exe = os.path.join(os.path.dirname(sys.executable), "dbt.exe")
sys.exit(subprocess.call([dbt_exe, *sys.argv[1:]], cwd=HERE))
