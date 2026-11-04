import os
import time
from Bio import Entrez
from google import genai
import xml.etree.ElementTree as ET

from config import *



def traduire_francais_vers_anglais(question_utilisateur_fr: str) -> str:
    prompt_system = f"""
    Tu es un expert en recherche bibliographique médicale. 
    Analyse la question en français ci-dessous et extrais uniquement les concepts médicaux majeurs (maximum 3 ou 4 concepts).
    Traduis ces concepts en anglais en utilisant le vocabulaire NATUREL et COURANT des chercheurs. 
    INTERDICTION absolue d'utiliser la syntaxe MeSH complexe.
    Relie-les avec l'opérateur "AND" et ajoute la balise "[tiab]" après chaque terme.
    Ne fais aucune phrase. Ne mets pas de guillemets. Donne uniquement la requête finale.
    
    Question : {question_utilisateur_fr}
    Requête PubMed :
    """
    reponse = client.models.generate_content(
        model="gemini-3.5-flash-lite", 
        contents=prompt_system
    )
    return reponse.text.strip()

# =========================================================================
# === 2. RECHERCHE ET TÉLÉCHARGEMENT OPTIMISÉ
# =========================================================================

def rechercher_pmid_articles(requete: str, nb_max_resultats: int) -> list[str]:
    #Recherche des identifiants (PMID) des articles
    print("Recherche des articles sur PubMed en cours...")
    connexion = Entrez.esearch(db="pubmed", term=requete, retmax=nb_max_resultats)
    resultats = Entrez.read(connexion)
    connexion.close()
    return resultats["IdList"]

def extraire_contexte_et_sources(liste_pmid: list[str]) -> tuple[str, list[dict]]:
    if not liste_pmid:
        return "", []

    print("Vérification de la disponibilité des textes intégraux...")
    # Requête elink groupée : Quels PMID possèdent un PMCID (texte intégral gratuit) ?
    conn_link = Entrez.elink(dbfrom="pubmed", db="pmc", id=liste_pmid, linkname="pubmed_pmc")
    liens = Entrez.read(conn_link)
    conn_link.close()

    mapping_pmc = {}
    for resultat in liens:
        pmid = resultat["IdList"][0]
        for lien_db in resultat.get("LinkSetDb", []):
            for lien in lien_db["Link"]:
                mapping_pmc[pmid] = lien["Id"] # Associe le PMID au PMCID

    pmcids_dispos = list(mapping_pmc.values())
    pmids_sans_texte = [pmid for pmid in liste_pmid if pmid not in mapping_pmc]

    textes_nettoyes = {}
    liste_sources = []

    # --- ÉTAPE A : Récupération groupée des textes intégraux (PMC) ---
    if pmcids_dispos:
        print(f"Téléchargement de {len(pmcids_dispos)} article(s) complet(s)...")
        conn_pmc = Entrez.efetch(db="pmc", id=pmcids_dispos, retmode="xml")
        xml_pmc = conn_pmc.read()
        conn_pmc.close()

        #Traduis en texte si le xml est en bytes
        if isinstance(xml_pmc, bytes): xml_pmc = xml_pmc.decode('utf-8')

        racine_pmc = ET.fromstring(xml_pmc)
        
        for article in racine_pmc.findall(".//article"):
            pmid, pmcid = "Inconnu", "Inconnu"
            for article_id in article.findall(".//article-id"):
                if article_id.get("pub-id-type") == "pmid": pmid = article_id.text.strip()
                elif article_id.get("pub-id-type") == "pmc": pmcid = article_id.text.strip()

            titre = "".join(article.find(".//article-title").itertext()) if article.find(".//article-title") is not None else "Aucun titre"
            resume = " ".join(article.find(".//abstract").itertext()) if article.find(".//abstract") is not None else "Aucun résumé"
            
            # Extraction propre des paragraphes du corps du texte
            paragraphes = [" ".join(p.itertext()) for p in article.findall(".//body//p")]
            corps = "\n".join(paragraphes)

            textes_nettoyes[pmid] = f"Titre: {titre}\nRésumé: {resume}\nCorps du texte:\n{corps}"
            liste_sources.append({
                "pmid": pmid, "titre": titre, "résumé": resume,
                "lien": f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/",
                "type": "Texte intégral"
            })

    # --- ÉTAPE B : Récupération groupée des résumés pour le reste (PubMed) ---
    if pmids_sans_texte:
        print(f"Téléchargement de {len(pmids_sans_texte)} résumé(s) (texte intégral indisponible)...")
        conn_pubmed = Entrez.efetch(db="pubmed", id=pmids_sans_texte, retmode="xml")
        xml_pubmed = conn_pubmed.read()
        conn_pubmed.close()
        
        if isinstance(xml_pubmed, bytes): xml_pubmed = xml_pubmed.decode('utf-8')
        racine_pubmed = ET.fromstring(xml_pubmed)

        for article in racine_pubmed.findall(".//PubmedArticle"):
            pmid_el = article.find(".//PMID")
            pmid = pmid_el.text.strip() if pmid_el is not None else "Inconnu"
            
            titre = "".join(article.find(".//ArticleTitle").itertext()) if article.find(".//ArticleTitle") is not None else "Aucun titre"
            resume = " ".join(article.find(".//Abstract").itertext()) if article.find(".//Abstract") is not None else "Aucun résumé"

            textes_nettoyes[pmid] = f"Titre: {titre}\nRésumé: {resume}"
            liste_sources.append({
                "pmid": pmid, "titre": titre, "résumé": resume,
                "lien": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "type": "Résumé uniquement"
            })

    # Assemblage du contexte final propre pour le LLM
    blocs_contexte = [f"--- SOURCE PMID: {s['pmid']} ({s['type']}) ---\n{textes_nettoyes.get(s['pmid'], '')}" for s in liste_sources]
    contexte_final = "\n\n".join(blocs_contexte)

    return contexte_final, liste_sources
