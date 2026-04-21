"""
SalamaIQ — Module IA (NVIDIA NIM / Qwen 3.5)
=============================================
Principe "Séparation des Cerveaux" :
  - Qwen = traducteur sémantique + générateur de texte UNIQUEMENT
  - Aucun calcul mathématique n'est confié à l'IA
  - Tous les calculs financiers restent dans Pandas (calculator.py)

Appels IA :
  1. map_columns()              → Mapping sémantique des colonnes
  2. generate_executive_summary() → Diagnostic IA (3 puces)
  3. answer_chat_question()     → Chat avec les données
"""

import os
import json
import re
from openai import OpenAI


# ─── Configuration Client NVIDIA NIM ─────────────────────────────────────────

MODEL_ID = "qwen/qwen3.5-122b-a10b"

def _get_client() -> OpenAI:
    """Retourne un client OpenAI configuré sur NVIDIA NIM."""
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise EnvironmentError("NVIDIA_API_KEY manquante dans les variables d'environnement.")
    return OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key
    )


def _extract_json(text: str) -> dict:
    """
    Extrait robustement un objet JSON depuis une réponse texte.
    Gère les cas où l'IA ajoute du texte avant/après le JSON.
    """
    # Chercher le premier objet JSON valide dans la réponse
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    # Tentative de parsing direct
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return {}


# ─── Appel #1 : Mapping Sémantique des Colonnes ──────────────────────────────

def map_columns(raw_headers: list) -> dict:
    """
    Mappe les colonnes brutes du fichier vers les variables standards SalamaIQ.

    Utilise response_format={"type": "json_object"} pour garantir
    un JSON valide sans parsing fragile.
    Fallback automatique sur regex si le modèle ne supporte pas le mode JSON.

    Args:
        raw_headers: Liste des noms de colonnes bruts du fichier source

    Returns:
        Dict {nom_colonne_brute: variable_standard}
    """
    system_prompt = """Tu es un expert en données financières de distribution de carburants.
Tu reçois une liste de noms de colonnes brutes extraites d'un fichier Excel ou CSV.
Tu dois identifier et mapper chaque colonne vers exactement une des variables standards suivantes :

Variables standards disponibles :
- datetransaction : Date de la transaction (date, jour, mois, période, exercice)
- fournisseur : Nom du fournisseur, distributeur, société d'approvisionnement, dépôt
- client : Nom du client, acheteur, station, bénéficiaire
- volume_gasoil : Volume de gasoil vendu (litres, m³, quantité GO, gasoil, diesel)
- volume_super : Volume de super sans plomb SP vendu (litres, m³, quantité SP, essence, super)
- marge_ht : Marge hors taxe, marge brute, commission, bénéfice HT
- ca_total : Chiffre d'affaires total, montant total, recette totale, total HT, facturé

RÈGLES ABSOLUES :
1. Réponds UNIQUEMENT avec un objet JSON valide, sans aucun autre texte ni markdown
2. Format strict : {"nom_colonne_brute": "variable_standard"}
3. N'inclus que les colonnes pour lesquelles tu es certain du mapping
4. Si une colonne ne correspond à aucune variable, ne l'inclus PAS
5. Ne crée pas de nouvelles clés, utilise uniquement les 7 variables définies ci-dessus"""

    user_prompt = f"Colonnes brutes à mapper (fichier carburant SMC Salama) : {json.dumps(raw_headers, ensure_ascii=False)}"

    valid_vars = {'datetransaction', 'fournisseur', 'client',
                  'volume_gasoil', 'volume_super', 'marge_ht', 'ca_total'}

    def _validate(mapping: dict) -> dict:
        """Garde seulement les mappings vers des variables standards reconnues."""
        return {k: v for k, v in mapping.items() if v in valid_vars}

    try:
        client = _get_client()

        # ── Tentative 1 : response_format json_object (garanti JSON) ──────────
        try:
            response = client.chat.completions.create(
                model=MODEL_ID,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt}
                ],
                response_format={"type": "json_object"},   # ← JSON garanti
                temperature=0.1,
                max_tokens=512
            )
            content = response.choices[0].message.content
            mapping = json.loads(content)   # parsing direct, pas de regex
            result = _validate(mapping)
            if result:
                print(f"[SalamaIQ] Mapping IA OK (JSON mode) : {result}")
                return result
        except Exception as json_mode_err:
            # Le modèle ne supporte pas response_format → on tente sans
            print(f"[SalamaIQ] JSON mode non supporté, fallback text mode: {json_mode_err}")

        # ── Tentative 2 : fallback sans response_format (parsing regex) ───────
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=512
        )
        content = response.choices[0].message.content.strip()
        mapping = _extract_json(content)
        result = _validate(mapping)
        print(f"[SalamaIQ] Mapping IA OK (text mode) : {result}")
        return result

    except Exception as e:
        print(f"[SalamaIQ] Erreur mapping IA (Qwen #1): {e}")
        return {}  # normalizer.py appliquera le fallback heuristique


# ─── Appel #2 : Diagnostic IA (Executive Summary) ────────────────────────────

def generate_executive_summary(kpi_data: dict) -> str:
    """
    Génère un diagnostic exécutif en 3 puces basé sur les KPIs calculés par Pandas.

    Args:
        kpi_data: Dictionnaire de KPIs et variations calculés par calculator.py

    Returns:
        Chaîne de 3 puces de diagnostic en français
    """
    system_prompt = """Tu es le Directeur Financier Analytique de la Société Marocaine des Carburants Salama (SMC Salama).
Tu reçois des données de performance calculées de manière fiable par un système Python/Pandas.
Tu dois rédiger un "Diagnostic Exécutif" destiné à la Direction Générale.

Format OBLIGATOIRE : exactement 3 bullet points HTML, chacun commençant par une icône emoji :
• Chaque puce : [ICÔNE EMOJI] **[Constat chiffré]** : [Analyse de la cause et orientation stratégique]
• Longueur : 2-3 phrases par puce maximum
• Ton : professionnel, direct, orienté décision
• Base-toi UNIQUEMENT sur les données fournies, ne fabrique aucun chiffre
• Mentionne les chiffres exacts fournis (CA, volumes, marges, variations %)"""

    # Préparer un résumé lisible pour l'IA
    kpi_summary = {
        "CA_Total_N": f"{kpi_data.get('ca_total', 0):,.0f} MAD",
        "CA_Total_N1": f"{kpi_data.get('ca_total_n1', 0):,.0f} MAD",
        "Variation_CA": f"{kpi_data.get('ca_variation', 0):+.1f}%" if kpi_data.get('ca_variation') is not None else "N/D",
        "Volume_Gasoil_N": f"{kpi_data.get('volume_gasoil', 0):,.0f} L",
        "Variation_Gasoil": f"{kpi_data.get('vol_gasoil_variation', 0):+.1f}%" if kpi_data.get('vol_gasoil_variation') is not None else "N/D",
        "Volume_Super_N": f"{kpi_data.get('volume_super', 0):,.0f} L",
        "Variation_Super": f"{kpi_data.get('vol_super_variation', 0):+.1f}%" if kpi_data.get('vol_super_variation') is not None else "N/D",
        "Marge_HT_N": f"{kpi_data.get('marge_ht', 0):,.0f} MAD",
        "Variation_Marge": f"{kpi_data.get('marge_variation', 0):+.1f}%" if kpi_data.get('marge_variation') is not None else "N/D",
        "Annee_Courante": kpi_data.get('current_year', 'N'),
        "Annee_Precedente": kpi_data.get('previous_year', 'N-1'),
        "Nombre_Transactions": kpi_data.get('total_transactions', 0),
        "Nombre_Clients": kpi_data.get('nb_clients', 0),
        "Nombre_Fournisseurs": kpi_data.get('nb_fournisseurs', 0),
    }

    user_prompt = f"Données de performance SMC Salama à analyser :\n{json.dumps(kpi_summary, ensure_ascii=False, indent=2)}"

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=800
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"[SalamaIQ] Erreur diagnostic IA (Qwen #2): {e}")
        return (
            "📊 **Données chargées et analysées avec succès** : "
            "Les KPIs et graphiques sont disponibles ci-dessous. "
            "L'analyse narrative automatisée est temporairement indisponible.\n\n"
            "🔄 **Service IA en cours de reconnexion** : "
            "Actualisez la page ou rechargez le fichier pour réessayer le diagnostic automatisé.\n\n"
            "✅ **Données fiables** : "
            "Tous les calculs (CA, volumes, marges) sont effectués par le moteur Pandas "
            "et garantis exacts au centime près."
        )


# ─── Appel #3 : Chat avec les Données ────────────────────────────────────────

def answer_chat_question(data_summary: dict, question: str) -> str:
    """
    Répond à une question de direction en se basant UNIQUEMENT sur le résumé JSON Pandas.

    Args:
        data_summary: Résumé statistique du DataFrame (calculé par Pandas, jamais par l'IA)
        question: Question posée par la direction

    Returns:
        Réponse concise et basée sur les données réelles
    """
    system_prompt = """Tu es l'Assistant Analytique de la Société Marocaine des Carburants Salama (SMC Salama).
Tu as accès aux données de vente réelles fournies en JSON, calculées par un système Python/Pandas fiable.

RÈGLES ABSOLUES DE RÉPONSE :
1. Base-toi UNIQUEMENT et exclusivement sur les données JSON fournies
2. Si l'information demandée n'est PAS dans le JSON, réponds exactement : "Cette information n'est pas disponible dans les données actuellement chargées."
3. Ne fabrique AUCUN chiffre, AUCUNE estimation, AUCUNE extrapolation
4. Sois très concis : 3 à 5 lignes maximum
5. Commence directement par la réponse, sans introduction
6. Utilise les chiffres exacts du JSON avec les unités appropriées (MAD, Litres, %)
7. Si plusieurs éléments sont demandés (top 3, etc.), liste-les avec leur valeur exacte"""

    user_prompt = f"""Données fiables actuelles (JSON Pandas) :
{json.dumps(data_summary, ensure_ascii=False, indent=2)}

Question de la Direction SMC Salama : {question}"""

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=512
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"[SalamaIQ] Erreur chat IA (Qwen #3): {e}")
        return (
            "⚠️ Le service d'analyse IA est temporairement indisponible. "
            "Veuillez consulter directement les KPI et graphiques du tableau de bord, "
            "ou réessayer dans quelques instants."
        )
