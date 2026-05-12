"""
SalamaIQ — Module de Normalisation Pandas (Mode Strict)
==========================================
Rejette les fichiers non conformes.
Applique le nettoyage strict (0.0 pour Qte, NaN pour Prix).
Convertit TTC en HT et calcule la marge unitaire.
"""

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = [
    'Date de Commande',
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
    'STATUT'
]

def normalize_dataframe(df: pd.DataFrame, ai_column_map: dict = None) -> tuple[pd.DataFrame, dict]:
    """
    Normalise le DataFrame selon le modèle strict exigé.
    """
    # 1. Vérification stricte des colonnes (ignorer la casse et les espaces superflus pour être robuste, mais chercher les exactes)
    # Pour éviter les erreurs de typographie invisibles, on nettoie d'abord les headers du DataFrame
    import re
    df.columns = [re.sub(r'\s+', ' ', str(c)).strip() for c in df.columns]
    
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Fichier non conforme. Colonnes obligatoires manquantes : {', '.join(missing_cols)}")

    df = df.copy()

    # 2. Nettoyage et typage
    def clean_numeric(val):
        if pd.isna(val) or val is None:
            return np.nan
        val_str = str(val).strip()
        if val_str in ('', '-', '—', 'N/A', 'n/a', '#N/A', 'nan', 'None'):
            return np.nan
        # Gestion des virgules et espaces européens
        cleaned = val_str.replace(' ', '').replace(',', '.')
        try:
            return float(cleaned)
        except ValueError:
            return np.nan

    # Quantités : Les valeurs vides/invalides deviennent 0.0
    qte_cols = ['Qte Gasoil 10 PPM/L', 'Qte SUPER SP/L']
    for col in qte_cols:
        df[col] = df[col].apply(clean_numeric).fillna(0.0)

    # Prix et Finance : Les valeurs vides/invalides deviennent NaN
    price_cols = [
        "Prix d'Achat Gasoil HT", "Prix d'Achat Super SP HT", 
        "Prix de Vente Gasoil TTC", "Prix de Vente Super TTC",
        "Marge Ht", "Montant FA TTC", "C.A", "ACHAT HT"
    ]
    for col in price_cols:
        df[col] = df[col].apply(clean_numeric)

    # 3. Calculs Métier
    df['prix_vente_gasoil_ht'] = df['Prix de Vente Gasoil TTC'] / 1.10
    df['prix_vente_super_ht'] = df['Prix de Vente Super TTC'] / 1.10
    
    # Marge unitaire avec protection division par 0
    total_qte = df['Qte Gasoil 10 PPM/L'] + df['Qte SUPER SP/L']
    df['marge_unitaire'] = np.where(total_qte > 0, df['Marge Ht'] / total_qte, np.nan)

    # 4. Parsing de la date
    df['datetransaction'] = pd.to_datetime(df['Date de Commande'], dayfirst=False, errors='coerce')
    df = df.dropna(subset=['datetransaction'])

    # 5. Nettoyage des chaînes de caractères (Client et Statut)
    for col in ['Client', 'STATUT']:
        df[col] = df[col].astype(str).str.upper().str.strip()
        df[col] = df[col].replace(r'\s+', ' ', regex=True)
        df.loc[df[col] == 'NAN', col] = 'INCONNU'

    # 6. Renommage vers le modèle de données interne
    rename_map = {
        'Client': 'client',
        'STATUT': 'statut',
        'Qte Gasoil 10 PPM/L': 'volume_gasoil',
        'Qte SUPER SP/L': 'volume_super',
        'Marge Ht': 'marge_ht',
        'Montant FA TTC': 'ca_total',
        'C.A': 'ca',
        'ACHAT HT': 'achat_ht',
        "Prix d'Achat Gasoil HT": 'prix_achat_gasoil_ht',
        "Prix d'Achat Super SP HT": 'prix_achat_super_ht',
        "Prix de Vente Gasoil TTC": 'prix_vente_gasoil_ttc',
        "Prix de Vente Super TTC": 'prix_vente_super_ttc',
    }
    df = df.rename(columns=rename_map)

    # Filtrer pour ne garder que les colonnes nécessaires (sécurité)
    final_cols = [
        'datetransaction', 'client', 'statut', 'volume_gasoil', 'volume_super', 
        'marge_ht', 'ca_total', 'ca', 'achat_ht', 'prix_achat_gasoil_ht', 
        'prix_achat_super_ht', 'prix_vente_gasoil_ttc', 'prix_vente_super_ttc', 
        'prix_vente_gasoil_ht', 'prix_vente_super_ht', 'marge_unitaire'
    ]
    df = df[final_cols]

    # Supprimer les lignes entièrement vides (sur la base de CA et volumes)
    df = df.dropna(subset=['ca_total', 'volume_gasoil', 'volume_super'], how='all')

    df = df.drop_duplicates().reset_index(drop=True)

    # Faux mapping retourné pour la compatibilité avec app.py
    return df, {}

