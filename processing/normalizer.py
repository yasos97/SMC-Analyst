"""
SalamaIQ — Module de Normalisation Pandas (Mode Tolérant)
==========================================================
Accepte plusieurs variantes de schémas (fichiers 2024 et 2025) grâce à un
système d'alias de colonnes.

Règles :
  - Les noms de colonnes sont normalisés (espaces/sauts de ligne compressés).
  - Chaque champ interne peut être alimenté par plusieurs noms sources (alias).
  - Quantités vides/invalides → 0.0 ; Prix/finance vides → NaN.
  - Conversion TTC → HT et calcul de la marge unitaire.
  - STATUT et Fournisseur sont OPTIONNELS (valeur par défaut si absents).
"""

import re
import numpy as np
import pandas as pd
from datetime import datetime
from difflib import get_close_matches

# ── Modèle de données interne ────────────────────────────────────────────────
# Pour chaque champ interne, on liste les en-têtes sources acceptés (alias).
# Les comparaisons se font après normalisation des espaces et en casse insensible.
COLUMN_ALIASES = {
    'datetransaction':        ['Date de Commande', 'Date', 'Date Commande', 'Date doc.'],
    'fournisseur':            ['Fournisseur CARB', 'Fournisseur', 'Fournisseur Carb'],
    'prix_achat_gasoil_ht':   ["Prix d'Achat Gasoil HT", "Prix d Achat Gasoil HT"],
    'prix_achat_super_ht':    ["Prix d'Achat Super SP HT", "Prix d Achat Super SP HT"],
    'client':                 ['Client', "Donneur d'ordre"],
    'volume_gasoil':          ['Qte Gasoil 10 PPM/L', 'Gasoil 10 PPM V', 'Qte Gasoil', 'Gasoil 10 PPM/L', 'volume_gasoil_sap'],
    'volume_super':           ['Qte SUPER SP/L', 'SUPER SP V', 'Qte Super', 'Super SP/L', 'volume_super_sap'],
    'marge_ht':               ['Marge Ht', 'Marge HT'],
    'prix_vente_gasoil_ttc':  ['Prix de Vente Gasoil TTC'],
    'prix_vente_super_ttc':   ['Prix de Vente Super TTC'],
    'ca_total':               ['Montant FA TTC', 'Montant Facture TTC', 'Val.nette'],
    'ca':                     ['C.A', 'CA', 'C A'],
    'achat_ht':               ['ACHAT HT', 'Achat HT'],
    'statut':                 ['STATUT', 'Statut', 'Statut Client', 'Segment', 'TDVt'],
}

# Fusion des variantes orthographiques connues (clé = forme sans espace en
# majuscules → valeur = forme canonique). Évite les doublons fournisseurs.
SUPPLIER_CANONICAL = {
    'REDAZILUB': 'REDAZI LUB',
}

# Champs strictement nécessaires pour qu'un fichier soit exploitable.
CORE_FIELDS = ['datetransaction', 'client']

# Au moins un champ de chaque groupe doit être présent.
CORE_GROUPS = {
    'volume': ['volume_gasoil', 'volume_super'],
    'finance': ['ca_total', 'ca', 'marge_ht'],
}


CLIENT_SEGMENT_MAPPING = {
    'JAK TRANSPO': 'Industriel',
    'SOMACOST': 'Industriel',
    'SOMALEV': 'Industriel',
    
    'AGASTAT': 'Réseau',
    'DRISSI': 'Réseau',
    'S/S': 'Réseau',
    'N ALI': 'Réseau',
    
    'AR PETROLE': 'Industriel',
    'BLACK OIL': 'Industriel',
    'CASALUB': 'Industriel',
    'DIMALUB': 'Industriel',
    'GALITRA': 'Industriel',
    'MADES': 'Industriel',
    'MFT': 'Industriel',
    'PETRONIC': 'Industriel',
    'REDAZI': 'Industriel',
    'SK POWER': 'Industriel',
    'STE CATER': 'Industriel',
    'STE DES CARB': 'Industriel',
    'ZAMAN': 'Industriel'
}

def _assign_segment(client_name: str) -> str:
    if pd.isna(client_name):
        return 'NON RENSEIGNÉ'
    c = str(client_name).upper()
    for key, segment in CLIENT_SEGMENT_MAPPING.items():
        if key.upper() in c:
            return segment.upper()
    return 'NON RENSEIGNÉ'

# Modèle d'import présenté à l'utilisateur (téléchargement Excel).

REQUIRED_COLUMNS = [
    'Date de Commande',
    'Fournisseur CARB',
    "Prix d'Achat Gasoil HT",
    "Prix d'Achat Super SP HT",
    'Client',
    'Qte Gasoil 10 PPM/L',
    'Qte SUPER SP/L',
    'Marge Ht',
    'Prix de Vente Gasoil TTC',
    'Prix de Vente Super TTC',
    'Montant FA TTC',
    'C.A',
    'ACHAT HT',
    'STATUT',
]


def _norm_key(s: str) -> str:
    """Normalise un nom de colonne pour la comparaison (espaces + casse)."""
    return re.sub(r'\s+', ' ', str(s)).strip().lower()


def _resolve_columns(df: pd.DataFrame) -> dict:
    """
    Construit un mapping {champ_interne: nom_colonne_source} à partir des alias.
    Retourne uniquement les champs effectivement trouvés dans le fichier.
    """
    # Index des colonnes présentes : clé normalisée -> nom réel
    present = {_norm_key(c): c for c in df.columns}
    mapping = {}
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            key = _norm_key(alias)
            if key in present:
                mapping[field] = present[key]
                break
    return mapping


def _clean_numeric(val):
    """Convertit une valeur en float, NaN si impossible."""
    if pd.isna(val) or val is None:
        return np.nan
    val_str = str(val).strip()
    if val_str in ('', '-', '—', 'N/A', 'n/a', '#N/A', 'nan', 'None'):
        return np.nan
        
    val_str = val_str.replace(' ', '').replace(' ', '')
    
    if ',' in val_str and '.' in val_str:
        if val_str.rfind(',') > val_str.rfind('.'):
            val_str = val_str.replace('.', '').replace(',', '.')
        else:
            val_str = val_str.replace(',', '')
    else:
        val_str = val_str.replace(',', '.')
        
    try:
        return float(val_str)
    except ValueError:
        return np.nan


def _robust_date_parser(val):
    if pd.isna(val) or val is None:
        return pd.NaT
    if isinstance(val, (pd.Timestamp, datetime)):
        return val
    val_str = str(val).strip()
    # Format standard DD/MM/YYYY en premier (pour le format SAP 05.01.2026 et autres)
    d = pd.to_datetime(val_str, dayfirst=True, errors='coerce')
    if pd.isna(d):
        d = pd.to_datetime(val_str, format='%m/%d/%Y', errors='coerce')
    return d


def normalize_dataframe(df: pd.DataFrame, ai_column_map: dict = None, existing_clients: list = None) -> tuple[pd.DataFrame, dict, dict]:
    """
    Normalise le DataFrame vers le modèle interne, en tolérant plusieurs schémas.

    Returns:
        (DataFrame normalisé, mapping {champ_interne: colonne_source}, corrections {ancien: nouveau})
    Raises:
        ValueError si les champs essentiels sont introuvables.
    """
    # 1. Normalisation des noms de colonnes (compresse \n et espaces multiples)
    df = df.copy()
    df.columns = [re.sub(r'\s+', ' ', str(c)).strip() for c in df.columns]

    # 1.5 Prétraitement spécifique SAP (Article / Quantité d'ordre)
    col_article = next((c for c in df.columns if 'article' in c.lower()), None)
    col_qte = next((c for c in df.columns if 'quantit' in c.lower() and 'ordre' in c.lower()), None)
    
    if col_article and col_qte:
        # Convertir en string robuste et gérer le NaN
        article_series = df[col_article].astype(str).str.upper()
        # Supprimer le point des milliers généré par SAP (ex: 34.000 -> 34000)
        qte_series = df[col_qte].astype(str).str.replace('.', '', regex=False)
        df['volume_gasoil_sap'] = np.where(article_series.str.contains('GASOIL'), qte_series, 0.0)
        df['volume_super_sap'] = np.where(article_series.str.contains('SUPER'), qte_series, 0.0)

    # 2. Résolution des colonnes via alias
    mapping = _resolve_columns(df)

    # 3. Vérification des champs essentiels
    missing_core = [f for f in CORE_FIELDS if f not in mapping]
    if missing_core:
        labels = {f: COLUMN_ALIASES[f][0] for f in missing_core}
        raise ValueError(
            "Fichier non conforme. Colonnes essentielles introuvables : "
            + ', '.join(labels.values())
        )

    for group, fields in CORE_GROUPS.items():
        if not any(f in mapping for f in fields):
            attendus = ' ou '.join(COLUMN_ALIASES[f][0] for f in fields)
            raise ValueError(
                f"Fichier non conforme. Aucune colonne de type « {group} » trouvée "
                f"(attendu : {attendus})."
            )

    # 4. Construction du DataFrame interne, champ par champ
    out = pd.DataFrame(index=df.index)

    # Date
    out['datetransaction'] = df[mapping['datetransaction']].apply(_robust_date_parser)

    # Quantités (NaN → 0.0)
    for vol in ('volume_gasoil', 'volume_super'):
        if vol in mapping:
            out[vol] = df[mapping[vol]].apply(_clean_numeric).fillna(0.0)
        else:
            out[vol] = 0.0

    # Prix et finance (NaN conservés)
    price_fields = [
        'prix_achat_gasoil_ht', 'prix_achat_super_ht',
        'prix_vente_gasoil_ttc', 'prix_vente_super_ttc',
        'marge_ht', 'ca_total', 'ca', 'achat_ht',
    ]
    for f in price_fields:
        out[f] = df[mapping[f]].apply(_clean_numeric) if f in mapping else np.nan

    # Texte : client (obligatoire), statut + fournisseur (optionnels)
    out['client'] = df[mapping['client']]
    
    # Text normalization for client and fournisseur
    out['fournisseur'] = df[mapping['fournisseur']] if 'fournisseur' in mapping else 'NON RENSEIGNÉ'
    for col, default in (('client', 'INCONNU'), ('fournisseur', 'NON RENSEIGNÉ')):
        out[col] = out[col].astype(str).str.upper().str.strip()
        out[col] = out[col].replace(r'\s+', ' ', regex=True)
        out.loc[out[col].isin(['NAN', 'NONE', '']), col] = default.upper()

    corrections = {}
    if existing_clients:
        # Fuzzy matching sur les clients
        existing_upper = [str(c).upper() for c in existing_clients if str(c).strip()]
        unique_clients = out['client'].unique()
        
        for c in unique_clients:
            if c == 'INCONNU' or pd.isna(c):
                continue
            matches = get_close_matches(str(c), existing_upper, n=1, cutoff=0.85)
            if matches and matches[0] != c:
                best_match = matches[0]
                corrections[c] = best_match
                # Apply correction
                out.loc[out['client'] == c, 'client'] = best_match

    # Auto-assign Statut based on Client name mapping
    file_statut = df[mapping['statut']] if 'statut' in mapping else pd.Series(['NON RENSEIGNÉ']*len(df), index=df.index)
    file_statut = file_statut.astype(str).str.upper().str.strip().replace(r'\s+', ' ', regex=True)
    file_statut[file_statut.isin(['NAN', 'NONE', ''])] = 'NON RENSEIGNÉ'

    out['statut'] = out['client'].apply(_assign_segment)
    mask_not_found = out['statut'] == 'NON RENSEIGNÉ'
    out.loc[mask_not_found, 'statut'] = file_statut[mask_not_found]
    
    # Mapper explicitement ZCB1/ZCB2 de SAP et supprimer REVENDEUR
    out['statut'] = out['statut'].astype(str).str.upper()
    out['statut'] = out['statut'].replace({'ZCB1': 'RÉSEAU', 'ZCB2': 'INDUSTRIEL', 'REVENDEUR': 'INDUSTRIEL'})

    # Canonicalisation des noms de fournisseurs (fusion des variantes connues)
    out['fournisseur'] = out['fournisseur'].apply(
        lambda v: SUPPLIER_CANONICAL.get(str(v).replace(' ', ''), v)
    )

    # 4.5 Regroupement par transaction (fusion des lignes Gasoil et Super du même jour/client)
    group_cols = ['datetransaction', 'client', 'statut', 'fournisseur']
    agg_dict = {
        'volume_gasoil': 'sum',
        'volume_super': 'sum',
        'ca_total': 'sum',
        'ca': 'sum',
        'marge_ht': 'sum',
        'prix_achat_gasoil_ht': 'max',
        'prix_achat_super_ht': 'max',
        'prix_vente_gasoil_ttc': 'max',
        'prix_vente_super_ttc': 'max'
    }
    agg_dict = {k: v for k, v in agg_dict.items() if k in out.columns}
    out = out.groupby(group_cols, dropna=False).agg(agg_dict).reset_index()

    # 5. Calculs métier
    out['prix_vente_gasoil_ht'] = out['prix_vente_gasoil_ttc'] / 1.10
    out['prix_vente_super_ht'] = out['prix_vente_super_ttc'] / 1.10
    
    # Pour les fichiers SAP, Val.nette (ca_total) sert aussi de CA HT
    out['ca'] = out['ca'].fillna(out['ca_total'])

    total_qte = out['volume_gasoil'] + out['volume_super']
    out['marge_unitaire'] = np.where(total_qte > 0, out['marge_ht'] / total_qte, np.nan)

    # 6. Nettoyage final
    out = out.dropna(subset=['datetransaction'])
    out = out.dropna(subset=['ca_total', 'volume_gasoil', 'volume_super'], how='all')
    out = out.drop_duplicates().reset_index(drop=True)

    return out, mapping, corrections
