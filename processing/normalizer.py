"""
SalamaIQ — Module de Normalisation Pandas
==========================================
Nettoie, renomme et restructure le DataFrame brut.

Règle absolue : datetransaction est TOUJOURS placé en première colonne.
Fallback heuristique si le mapping IA est vide ou incomplet.

Parsing numérique (3 niveaux de fiabilité) :
  1. Babel  — locale-aware, gère fr_MA / fr_FR / en_US
  2. Regex  — nettoyage brut des caractères parasites
  3. np.nan — si toujours impossible
"""

import re
import warnings
import difflib
import numpy as np
import pandas as pd

# Babel — parsing de nombres locale-aware (pip install babel)
try:
    from babel.numbers import parse_decimal
    from decimal import InvalidOperation, Decimal
    _BABEL_AVAILABLE = True
except ImportError:
    _BABEL_AVAILABLE = False
    warnings.warn("[SalamaIQ] babel non installé — fallback regex uniquement. pip install babel")


# ─── Variables standards et leurs mots-clés heuristiques ─────────────────────

HEURISTIC_PATTERNS = {
    'datetransaction': [
        r'date', r'jour', r'mois', r'period', r'exercice', r'dt', r'day'
    ],
    'fournisseur': [
        r'fourni', r'supplier', r'distrib', r'depot', r'dépôt', r'source',
        r'origine', r'vendeur', r'societ', r'société'
    ],
    'client': [
        r'client', r'achet', r'station', r'bénéfici', r'benefici',
        r'destinat', r'customer', r'buyer'
    ],
    'volume_gasoil': [
        r'gasoil', r'diesel', r'go\b', r'gazole', r'vol.*gas', r'qte.*go',
        r'quantit.*go', r'litr.*go'
    ],
    'volume_super': [
        r'super', r'sp\b', r'sans.*plomb', r'essence', r'vol.*sp',
        r'qte.*sp', r'quantit.*sp', r'litr.*sp'
    ],
    'marge_ht': [
        r'marge', r'margin', r'commission', r'bénéfice', r'benefice',
        r'profit', r'gain', r'marge.*ht', r'marge.*brut'
    ],
    'ca_total': [
        r'ca\b', r'chiffre', r'affaire', r'total', r'montant', r'recette',
        r'factur', r'ht\b', r'revenus', r'revenue', r'ca_total'
    ],
}

STANDARD_COLUMN_ORDER = [
    'datetransaction', 'fournisseur', 'client',
    'volume_gasoil', 'volume_super', 'marge_ht', 'ca_total'
]


def _heuristic_mapping(headers: list) -> dict:
    """
    Fallback : mappe les colonnes par correspondance de mots-clés regex.
    Utilisé quand l'API IA est indisponible ou le mapping incomplet.
    """
    mapping = {}
    used_targets = set()

    for header in headers:
        header_lower = str(header).lower().strip()
        # Normaliser : retirer accents pour comparaison
        header_norm = re.sub(r'[^\w\s]', '', header_lower)

        best_match = None
        best_score = 0

        for target, patterns in HEURISTIC_PATTERNS.items():
            if target in used_targets:
                continue
            for pattern in patterns:
                if re.search(pattern, header_norm, re.IGNORECASE):
                    score = len(pattern)
                    if score > best_score:
                        best_score = score
                        best_match = target

        if best_match and best_score > 0:
            mapping[header] = best_match
            used_targets.add(best_match)

    return mapping

# Locales candidates pour le parsing (ordre de priorité : Maroc → France → UK → US)
_LOCALES = ['fr_MA', 'fr_FR', 'ar_MA', 'fr', 'en_US']


def _clean_numeric(value) -> float:
    """
    Parse une valeur numérique avec 3 niveaux de fiabilité :

    Niveau 1 — Babel (locale-aware) :
      Gère automatiquement tous les formats :
      - '1 234,56'  (espace + virgule décimale → format fr_MA)
      - '1.234,56'  (point milliers + virgule décimale → format européen)
      - '1,234.56'  (virgule milliers + point décimale → format anglais)
      - '(1 500,00)' (négatifs entre parenthèses → format comptable)
      - '12,5%'     (pourcentage → divisé par 100)
      - '-1 234'    (négatif standard)

    Niveau 2 — Regex brut :
      Nettoyage des caractères parasites avec heuristique virgule/point.

    Niveau 3 — np.nan si toujours impossible.
    """
    if pd.isna(value) or value is None:
        return np.nan

    val_str = str(value).strip()

    # Valeur vide ou tiret (cellule vide dans Excel)
    if val_str in ('', '-', '—', 'N/A', 'n/a', '#N/A', 'nan', 'None'):
        return np.nan

    # Déjà un int/float Python
    if isinstance(value, (int, float)):
        return float(value) if not (isinstance(value, float) and np.isnan(value)) else np.nan

    # Heuristique pré-Babel si les deux séparateurs sont présents
    if ',' in val_str and '.' in val_str:
        neg = val_str.startswith('-') or (val_str.startswith('(') and val_str.endswith(')'))
        cleaned = re.sub(r'[^\d,.]', '', val_str)
        last_comma = cleaned.rfind(',')
        last_dot = cleaned.rfind('.')
        if last_comma > last_dot:
            cleaned = cleaned.replace('.', '').replace(',', '.')
        else:
            cleaned = cleaned.replace(',', '')
        try:
            res = float(cleaned)
            return -res if neg else res
        except ValueError:
            pass

    # ── Niveau 1 : Babel locale-aware ────────────────────────────────────────
    if _BABEL_AVAILABLE:
        # Gérer les négatifs entre parenthèses comptables : (1 500,00) → -1500.00
        negative_parens = val_str.startswith('(') and val_str.endswith(')')
        val_to_parse = val_str[1:-1].strip() if negative_parens else val_str

        # Supprimer le signe % avant le parsing Babel
        is_percent = val_to_parse.endswith('%')
        if is_percent:
            val_to_parse = val_to_parse[:-1].strip()

        for locale in _LOCALES:
            try:
                result = float(parse_decimal(val_to_parse, locale=locale))
                if is_percent:
                    result = result / 100.0
                return -result if negative_parens else result
            except (InvalidOperation, ValueError, Exception):
                continue

    # ── Niveau 2 : Regex robuste ──────────────────────────────────────────────
    # Supprimer tout sauf chiffres, virgule, point, signe négatif
    neg = val_str.startswith('-') or (val_str.startswith('(') and val_str.endswith(')'))
    cleaned = re.sub(r'[^\d,.]', '', val_str)

    if not cleaned:
        return np.nan

    if ',' in cleaned:            # "1234,56" ou "1 234,56" → virgule = décimale
        cleaned = cleaned.replace(',', '.')

    try:
        result = float(cleaned)
        return -result if neg else result
    except ValueError:
        return np.nan


def _deduplicate_strings(series: pd.Series, cutoff: float = 0.90) -> pd.Series:
    """
    Dédoublonne intelligemment une série de textes en fusionnant les variantes
    très similaires (fautes de frappe, espaces manquants) vers la variante
    la plus fréquemment observée.
    """
    # 1. Obtenir les valeurs uniques triées par fréquence (de la plus haute à la plus basse)
    counts = series.value_counts()
    unique_vals = counts.index.tolist()
    
    mapping = {}
    master_targets = []  # Les vrais noms distincts gardés
    
    for val in unique_vals:
        if pd.isna(val) or str(val).strip() == '':
            mapping[val] = val
            continue
            
        str_val = str(val)
        
        # Chercher si cette valeur ressemble à un maître déjà sélectionné
        matches = difflib.get_close_matches(str_val, master_targets, n=1, cutoff=cutoff)
        
        if matches:
            # Si oui, on la rattache au maître trouvé (qui avait une plus grande fréquence)
            mapping[val] = matches[0]
        else:
            # Sinon, c'est une nouvelle entité distincte
            master_targets.append(str_val)
            mapping[val] = str_val
            
    return series.map(mapping)



def normalize_dataframe(df: pd.DataFrame, ai_column_map: dict) -> tuple[pd.DataFrame, dict]:
    """
    Normalise le DataFrame en 4 étapes :
      1. Fusion mapping IA + fallback heuristique
      2. Renommage des colonnes vers les variables standards
      3. Réorganisation : datetransaction TOUJOURS en première colonne
      4. Nettoyage numérique + parsing des dates

    Args:
        df: DataFrame brut (issu d'ingestion.py)
        ai_column_map: Mapping IA {colonne_brute: variable_standard}

    Returns:
        Tuple (DataFrame normalisé, dict de mapping final utilisé)
    """
    df = df.copy()

    # ── Étape 1 : Fusion mapping IA + heuristique ─────────────────────────────
    # Le mapping IA est prioritaire ; pour les colonnes non mappées, on utilise l'heuristique
    unmapped_headers = [h for h in df.columns if h not in ai_column_map]
    heuristic_map = _heuristic_mapping(unmapped_headers)

    # Éviter les conflits : si une variable standard est déjà mappée par l'IA, ne pas l'écraser
    ai_targets = set(ai_column_map.values())
    final_map = dict(ai_column_map)
    for col, target in heuristic_map.items():
        if target not in ai_targets:
            final_map[col] = target
            ai_targets.add(target)

    # ── Étape 2 : Renommage des colonnes (avec garantie d'unicité) ────────────
    valid_map = {k: v for k, v in final_map.items() if k in df.columns}
    unique_target_map = {}
    used_targets = set()
    for k, v in valid_map.items():
        if v not in used_targets:
            unique_target_map[k] = v
            used_targets.add(v)
            
    df = df.rename(columns=unique_target_map)

    # ── Étape 3 : Réorganisation — datetransaction TOUJOURS en premier ────────
    existing_standard = [c for c in STANDARD_COLUMN_ORDER if c in df.columns]
    other_cols = [c for c in df.columns if c not in STANDARD_COLUMN_ORDER]
    df = df[existing_standard + other_cols]

    # ── Étape 4a : Nettoyage numérique ───────────────────────────────────────
    numeric_cols = ['volume_gasoil', 'volume_super', 'marge_ht', 'ca_total']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].apply(_clean_numeric)

    # ── Étape 4b : Parsing des dates ─────────────────────────────────────────
    if 'datetransaction' in df.columns:
        # Parsing des dates au format MM/JJ/AAAA (format Excel de l'entreprise)
        df['datetransaction'] = pd.to_datetime(
            df['datetransaction'], dayfirst=False, errors='coerce'
        )
        # Supprimer les lignes sans date valide
        df = df.dropna(subset=['datetransaction'])

    # ── Étape 4c : Nettoyage des chaînes de caractères (Clients / Fournisseurs) ──
    for col in ['client', 'fournisseur']:
        if col in df.columns:
            # Uppercase, strip les espaces aux extrémités, et remplacer espaces multiples par un seul
            df[col] = df[col].astype(str).str.upper().str.strip()
            df[col] = df[col].replace(r'\s+', ' ', regex=True)
            # Traiter les nan transformés en string par astype
            df.loc[df[col] == 'NAN', col] = 'INCONNU'
            
            # Application du Fuzzy Matching (dédoublonnage intelligent)
            df[col] = _deduplicate_strings(df[col], cutoff=0.90)

    # ── Étape 5 : Nettoyage final ─────────────────────────────────────────────
    # Supprimer les lignes entièrement vides
    df = df.dropna(how='all')
    # Supprimer les lignes dupliquées
    df = df.drop_duplicates()
    # Reset index
    df = df.reset_index(drop=True)

    return df, final_map
