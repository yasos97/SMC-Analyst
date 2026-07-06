"""
SalamaIQ — Module d'Ingestion Universelle
==========================================
Lit tout fichier .xlsx, .xls ou .csv quelle que soit sa structure.
Auto-détecte l'encodage, les en-têtes, et les lignes vides.
"""

import os
import re
import chardet
import pandas as pd


def _detect_header_row(df_raw: pd.DataFrame) -> int:
    """
    Détecte automatiquement la ligne d'en-tête :
    recherche la première ligne ayant le plus de valeurs non-nulles.
    """
    best_row = 0
    best_score = 0
    # Analyser les 15 premières lignes maximum
    for i in range(min(15, len(df_raw))):
        row = df_raw.iloc[i]
        # Score = nombre de cellules non-nulles ET non-numériques (signes d'en-tête)
        score = sum(1 for v in row if pd.notna(v) and str(v).strip() != '')
        text_score = sum(1 for v in row if pd.notna(v) and re.search(r'[a-zA-ZÀ-ÿ]', str(v)))
        combined = score + (text_score * 2)
        if combined > best_score:
            best_score = combined
            best_row = i
    return best_row


def read_file(filepath: str) -> tuple[pd.DataFrame, list]:
    """
    Lit un fichier xlsx/xls/csv avec gestion des structures variables.

    Args:
        filepath: Chemin absolu vers le fichier

    Returns:
        Tuple (DataFrame brut, liste d'en-têtes bruts)

    Raises:
        RuntimeError: Si le fichier ne peut pas être lu
    """
    ext = os.path.splitext(filepath)[1].lower()

    try:
        # ── Lecture brute sans aucun en-tête supposé ─────────────────────────
        if ext in ['.xlsx', '.xlsm']:
            df_raw = pd.read_excel(filepath, header=None)
        elif ext in ['.xls']:
            try:
                df_raw = pd.read_excel(filepath, header=None, engine='xlrd')
            except Exception as e:
                # Fallback pour les fichiers SAP (.XLS qui sont en réalité des TSV UTF-16)
                df_raw = pd.read_csv(filepath, header=None, encoding='utf-16', sep='\t', dtype=str)
        elif ext == '.csv':
            # Auto-détection de l'encodage
            with open(filepath, 'rb') as f:
                raw_bytes = f.read(50_000)
            detected = chardet.detect(raw_bytes)
            encoding = detected.get('encoding') or 'utf-8'
            # Essai avec différents séparateurs
            for sep in [';', ',', '\t', '|']:
                try:
                    df_raw = pd.read_csv(
                        filepath, header=None, dtype=str,
                        encoding=encoding, sep=sep, engine='python'
                    )
                    if df_raw.shape[1] > 1:
                        break
                except Exception:
                    continue
        else:
            raise ValueError(f"Format non supporté: '{ext}'. Utilisez .xlsx, .xls ou .csv")

        if df_raw.empty:
            raise ValueError("Le fichier est vide.")

        # ── Détection automatique de la ligne d'en-têtes ─────────────────────
        header_row_idx = _detect_header_row(df_raw)
        raw_headers = [str(h).strip() for h in df_raw.iloc[header_row_idx].tolist()]

        # ── Construction du DataFrame avec les vraies colonnes ────────────────
        df = df_raw.iloc[header_row_idx + 1:].copy()
        df.columns = raw_headers
        df = df.reset_index(drop=True)

        # Supprimer les lignes et colonnes 100% vides
        df = df.dropna(how='all').dropna(axis=1, how='all')

        # SAP génère souvent des doublons parfaits (ex: même facture, même produit en double)
        df = df.drop_duplicates()

        # Filtrer les en-têtes pertinents (non vides, non numériques purs)
        valid_headers = [h for h in raw_headers if h and h.lower() not in ['nan', 'none', '']]

        return df, valid_headers

    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Impossible de lire le fichier '{os.path.basename(filepath)}': {str(e)}")
