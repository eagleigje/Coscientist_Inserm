import os
import time
from Bio import Entrez
from google import genai
import xml.etree.ElementTree as ET

from source import *
from config import *

# =========================================================================
# === SCRIPT PRINCIPAL (RAG)
# =========================================================================

if __name__ == "__main__":
    question = input("Quelle est votre question médicale : ")
    print("\n")

    print(f"Traduction de la question vers l'anglais ...\n")
    mots_cles = traduire_francais_vers_anglais(question)
    print(f"Mots-clés PubMed : {mots_cles}\n")

    liste_ids = rechercher_pmid_articles(mots_cles, NB_MAX_RESULTATS)

    if not liste_ids:
        print("Aucun article trouvé pour cette requête.")
    else:
        contexte_propre, sources = extraire_contexte_et_sources(liste_ids)

        prompt_system_rag = f"""
        Tu es un assistant médical expert et un chercheur scientifique rigoureux.
        
        CONSIGNES DE RÉPONSE :
        1. Rédige ta réponse entièrement en FRANÇAIS, de manière claire, structurée et professionnelle.
        2. Base ta réponse EXCLUSIVEMENT sur les extraits et articles scientifiques fournis ci-dessous.
        3. Exploite au maximum la précision technique du texte (mécanismes biologiques, biomarqueurs, résultats chiffrés, molécules, protocoles).
        4. Si les extraits ne contiennent pas les informations suffisantes pour répondre à la question, indique-le clairement et poliment sans inventer de faits.
        5. Structure ta réponse avec des sections claires (ex: synthèse, détails techniques/mécanismes, limites ou conclusions) et des puces si nécessaire.
                
        --- EXTRAITS SCIENTIFIQUES NETTOYÉS ---
        {contexte_propre}

        --- QUESTION ---
        {question}
        """

        print("\nRecherche sur PubMed / PMC d'articles en cours...")
        # On utilise flash "classique" (pas lite) pour un RAG performant sur des longs textes
        reponse_rag = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt_system_rag
        )

        print("\n================ RÉPONSE DU RAG ================\n")
        print(reponse_rag.text)
        print("\n==================== SOURCES ===================\n")
        
        for s in sources:
            print(f"- Titre : {s['titre']}")
            print(f"  Type  : {s['type']}")
            print(f"  Lien  : {s['lien']}\n")