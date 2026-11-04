from Bio import Entrez
from google import genai

# =========================================================================
# === CONFIGURATION
# =========================================================================

# Entrez votre adresse mail ici (obligatoire pour NCBI)
Entrez.email = ""

# Entrez votre clé API Gemini ici
CLE_API_GEMINI = ""
client = genai.Client(api_key=CLE_API_GEMINI)
MODEL_TRAD = "gemini-3.5-flash-lite"
MODEL_REPONSE = "gemini-3.5-flash"

NB_MAX_RESULTATS = 3
