"""
SalamaIQ — Moteur de Calcul Pandas
====================================
Principe absolu : Ce module est le SEUL moteur mathématique de SalamaIQ.
Aucun calcul numérique n'est délégué à l'IA.
Tous les résultats sont garantis exacts au centime près.
"""

import numpy as np
import pandas as pd
from datetime import datetime

try:
    from processing.forecaster import generate_forecast
except ImportError:
    generate_forecast = lambda vals, p: [0]*p

# ─── Utilitaires ─────────────────────────────────────────────────────────────

def _safe_sum(df: pd.DataFrame, col: str) -> float:
    """Somme sécurisée d'une colonne (retourne 0.0 si absente ou vide)."""
    if col in df.columns and not df.empty:
        return float(df[col].sum(skipna=True))
    return 0.0


def _calc_variation(current: float, previous: float) -> float | None:
    """
    Calcule la variation en % entre deux valeurs.
    Retourne None si la valeur précédente est 0 ou absente.
    """
    if previous and previous != 0:
        return round(((current - previous) / abs(previous)) * 100, 2)
    return None


def _split_by_year(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, int, int]:
    """Sépare le DataFrame en année courante (N) et précédente (N-1)."""
    if 'datetransaction' not in df.columns or df.empty:
        return df, pd.DataFrame(), datetime.now().year, datetime.now().year - 1

    # Déterminer l'année courante à partir des données (pas datetime.now())
    years_in_data = df['datetransaction'].dt.year.dropna().unique()
    years_in_data = sorted(years_in_data, reverse=True)

    if len(years_in_data) >= 2:
        current_year = int(years_in_data[0])
        previous_year = int(years_in_data[1])
    elif len(years_in_data) == 1:
        current_year = int(years_in_data[0])
        previous_year = current_year - 1
    else:
        current_year = datetime.now().year
        previous_year = current_year - 1

    df_n = df[df['datetransaction'].dt.year == current_year].copy()
    df_n1 = df[df['datetransaction'].dt.year == previous_year].copy()

    return df_n, df_n1, current_year, previous_year


# ─── KPIs Principaux ─────────────────────────────────────────────────────────

def compute_kpis(df: pd.DataFrame) -> dict:
    """
    Calcule l'ensemble des KPIs pour le dashboard.

    Returns:
        Dict complet avec valeurs N, N-1, variations, et métadonnées
    """
    df_n, df_n1, current_year, previous_year = _split_by_year(df)

    # ── Chiffre d'Affaires ───────────────────────────────────────────────────
    ca_n = _safe_sum(df_n, 'ca')
    ca_n1 = _safe_sum(df_n1, 'ca')
    ca_variation = _calc_variation(ca_n, ca_n1)

    # ── Volumes Gasoil ───────────────────────────────────────────────────────
    vol_gasoil_n = _safe_sum(df_n, 'volume_gasoil')
    vol_gasoil_n1 = _safe_sum(df_n1, 'volume_gasoil')
    vol_gasoil_variation = _calc_variation(vol_gasoil_n, vol_gasoil_n1)

    # ── Volumes Super SP ─────────────────────────────────────────────────────
    vol_super_n = _safe_sum(df_n, 'volume_super')
    vol_super_n1 = _safe_sum(df_n1, 'volume_super')
    vol_super_variation = _calc_variation(vol_super_n, vol_super_n1)

    # ── Marge HT ─────────────────────────────────────────────────────────────
    marge_n = _safe_sum(df_n, 'marge_ht')
    marge_n1 = _safe_sum(df_n1, 'marge_ht')
    marge_variation = _calc_variation(marge_n, marge_n1)

    # ── Volume Total ─────────────────────────────────────────────────────────
    vol_total_n = vol_gasoil_n + vol_super_n
    vol_total_n1 = vol_gasoil_n1 + vol_super_n1
    vol_total_variation = _calc_variation(vol_total_n, vol_total_n1)

    taux_marge_n = round((marge_n / ca_n * 100), 2) if ca_n > 0 else 0.0
    taux_marge_n1 = round((marge_n1 / ca_n1 * 100), 2) if ca_n1 > 0 else 0.0

    # ── Marge Unitaire ───────────────────────────────────────────────────────
    marge_unit_n = round(marge_n / vol_total_n, 4) if vol_total_n > 0 else 0.0
    marge_unit_n1 = round(marge_n1 / vol_total_n1, 4) if vol_total_n1 > 0 else 0.0
    marge_unit_variation = _calc_variation(marge_unit_n, marge_unit_n1)

    # ── Métadonnées ──────────────────────────────────────────────────────────
    date_debut = str(df['datetransaction'].min().date()) if 'datetransaction' in df.columns else 'N/D'
    date_fin = str(df['datetransaction'].max().date()) if 'datetransaction' in df.columns else 'N/D'
    nb_clients = int(df['client'].nunique()) if 'client' in df.columns else 0
    nb_statuts = int(df['statut'].nunique()) if 'statut' in df.columns else 0

    # ── KPIs Avancés pour la Variation Mois en Cours ────────────────────────
    current_month_kpis = {}
    if 'datetransaction' in df_n.columns and not df_n.empty:
        last_month = df_n['datetransaction'].dt.month.max()
        df_current_month = df_n[df_n['datetransaction'].dt.month == last_month]
        df_prev_month = df_n[df_n['datetransaction'].dt.month == (last_month - 1)] if last_month > 1 else pd.DataFrame()
        current_month_kpis = {
            'ca_month': _safe_sum(df_current_month, 'ca'),
            'ca_prev_month': _safe_sum(df_prev_month, 'ca'),
            'ca_month_variation': _calc_variation(
                _safe_sum(df_current_month, 'ca'),
                _safe_sum(df_prev_month, 'ca')
            ),
            'month_label': df_current_month['datetransaction'].dt.strftime('%B %Y').iloc[0]
                           if not df_current_month.empty else ''
        }

    return {
        # CA
        'ca_total': round(ca_n, 2),
        'ca_total_n1': round(ca_n1, 2),
        'ca_variation': ca_variation,
        # Volume Total
        'volume_total': round(vol_total_n, 2),
        'volume_total_n1': round(vol_total_n1, 2),
        'vol_total_variation': vol_total_variation,
        # Volume Gasoil
        'volume_gasoil': round(vol_gasoil_n, 2),
        'volume_gasoil_n1': round(vol_gasoil_n1, 2),
        'vol_gasoil_variation': vol_gasoil_variation,
        # Volume Super
        'volume_super': round(vol_super_n, 2),
        'volume_super_n1': round(vol_super_n1, 2),
        'vol_super_variation': vol_super_variation,
        # Marge
        'marge_ht': round(marge_n, 2),
        'marge_ht_n1': round(marge_n1, 2),
        'marge_variation': marge_variation,
        'taux_marge': taux_marge_n,
        'taux_marge_n1': taux_marge_n1,
        'marge_unitaire': marge_unit_n,
        'marge_unitaire_n1': marge_unit_n1,
        'marge_unitaire_variation': marge_unit_variation,
        # Années
        'current_year': current_year,
        'previous_year': previous_year,
        # Métadonnées
        'date_debut': date_debut,
        'date_fin': date_fin,
        'total_transactions': len(df),
        'nb_clients': nb_clients,
        'nb_statuts': nb_statuts,
        # Mois en cours
        **current_month_kpis,
    }


# ─── Séries Mensuelles (pour les graphiques) ─────────────────────────────────

def get_monthly_series(df: pd.DataFrame) -> dict:
    """
    Calcule les séries mensuelles pour les graphiques d'évolution multi-années.

    Returns:
        Dict avec labels et séries dynamiques par année pour CA, volumes, marge.
        Format: {'ca': {'2025': [...], '2024': [...]}, 'vol_gasoil': {...}, ...}
    """
    month_labels = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']
    months = list(range(1, 13))

    if 'datetransaction' not in df.columns or df.empty:
        return {
            'labels': month_labels,
            'ca': {}, 'vol_gasoil': {}, 'vol_super': {}, 'marge': {}
        }

    # Grouper par année
    years_in_data = sorted(df['datetransaction'].dt.year.dropna().unique().tolist(), reverse=True)
    
    # On limite à 5 années max pour la clarté visuelle
    years_to_process = years_in_data[:5]

    def monthly_agg_by_year(df_yr, col):
        if df_yr.empty or col not in df_yr.columns:
            return [0.0] * 12
        grp = df_yr.groupby(df_yr['datetransaction'].dt.month)[col].sum()
        return [round(float(grp.get(m, 0.0)), 2) for m in months]

    series = {
        'labels': month_labels,
        'ca': {},
        'vol_gasoil': {},
        'vol_super': {},
        'marge': {}
    }

    for yr in years_to_process:
        yr_str = str(int(yr))
        df_yr = df[df['datetransaction'].dt.year == yr]
        
        # On ne remplit que s'il y a des données, ou on remplit de zéros
        series['ca'][yr_str] = monthly_agg_by_year(df_yr, 'ca')
        series['vol_gasoil'][yr_str] = monthly_agg_by_year(df_yr, 'volume_gasoil')
        series['vol_super'][yr_str] = monthly_agg_by_year(df_yr, 'volume_super')
        series['marge'][yr_str] = monthly_agg_by_year(df_yr, 'marge_ht')

    return series


# ─── Top 10 Clients ───────────────────────────────────────────────────────────

def get_top10_clients(df: pd.DataFrame) -> list:
    """
    Retourne le Top 10 des clients par CA total pour l'année courante (avec delta N-1).
    """
    if 'client' not in df.columns or df.empty:
        return []

    df_n, df_n1, current_year, previous_year = _split_by_year(df)
    
    if df_n.empty:
        return []

    agg_dict = {}
    if 'ca' in df_n.columns:
        agg_dict['ca'] = 'sum'
    if 'volume_gasoil' in df_n.columns:
        agg_dict['volume_gasoil'] = 'sum'
    if 'volume_super' in df_n.columns:
        agg_dict['volume_super'] = 'sum'
    if 'marge_ht' in df_n.columns:
        agg_dict['marge_ht'] = 'sum'

    if not agg_dict:
        return []

    top_n = df_n.groupby('client').agg(agg_dict)
    
    ca_n1_dict = {}
    if not df_n1.empty and 'ca' in df_n1.columns:
        top_n1 = df_n1.groupby('client')['ca'].sum()
        ca_n1_dict = top_n1.to_dict()

    sort_col = 'ca' if 'ca' in top_n.columns else list(top_n.columns)[0]
    top_n = top_n.nlargest(10, sort_col).reset_index()

    result = []
    for _, row in top_n.iterrows():
        client_name = str(row['client'])
        ca_n = float(row.get('ca', 0))
        ca_n1 = float(ca_n1_dict.get(client_name, 0))
        
        variation = None
        if ca_n1 > 0:
            variation = round(((ca_n - ca_n1) / ca_n1) * 100, 1)

        item = {
            'client': client_name,
            'ca': round(ca_n, 2),
            'ca_variation': variation,
            'volume_gasoil': round(float(row.get('volume_gasoil', 0)), 2),
            'volume_super': round(float(row.get('volume_super', 0)), 2),
            'marge': round(float(row.get('marge_ht', 0)), 2),
        }
        result.append(item)

    return result


# ─── Bridge Chart (Marge par Segment/Fournisseur) ────────────────────────────

def get_margin_bridge(df: pd.DataFrame) -> dict:
    """
    Calcule les données pour le Bridge Chart (Waterfall) de marge par fournisseur.

    Returns:
        Dict avec categories, values, et totaux pour le waterfall
    """
    if 'marge_ht' not in df.columns or df.empty:
        return {'categories': [], 'values': [], 'total': 0.0}

    group_col = 'fournisseur' if 'fournisseur' in df.columns else 'client'

    if group_col not in df.columns:
        return {'categories': [], 'values': [], 'total': 0.0}

    bridge = df.groupby(group_col)['marge_ht'].sum().reset_index()
    bridge.columns = ['segment', 'marge']
    bridge = bridge.sort_values('marge', ascending=False).head(8)

    total = round(float(bridge['marge'].sum()), 2)

    return {
        'categories': [str(r['segment']) for _, r in bridge.iterrows()],
        'values': [round(float(r['marge']), 2) for _, r in bridge.iterrows()],
        'total': total,
    }


# ─── Mix Produits (Donut) ─────────────────────────────────────────────────────

def get_product_mix(df: pd.DataFrame) -> dict:
    """
    Répartition Gasoil vs Super SP en volume et CA.
    Utilisé pour le Donut Chart 'Mix Produits'.
    """
    vol_go = _safe_sum(df, 'volume_gasoil')
    vol_sp = _safe_sum(df, 'volume_super')
    total_vol = vol_go + vol_sp

    ca_go = 0.0
    ca_sp = 0.0
    # Estimation proportionnelle du CA par produit (si le CA global et les volumes sont disponibles)
    if total_vol > 0 and 'ca_total' in df.columns:
        ca_total = _safe_sum(df, 'ca_total')
        ca_go = round(ca_total * (vol_go / total_vol), 2)
        ca_sp = round(ca_total * (vol_sp / total_vol), 2)

    return {
        'labels': ['Gasoil', 'Super SP'],
        'volumes': [round(vol_go, 2), round(vol_sp, 2)],
        'pct_volumes': [
            round(vol_go / total_vol * 100, 1) if total_vol > 0 else 0,
            round(vol_sp / total_vol * 100, 1) if total_vol > 0 else 0,
        ],
        'ca_estime': [ca_go, ca_sp],
        'total_volume': round(total_vol, 2),
    }


# ─── Série Cumulative CA (Step Area) ─────────────────────────────────────────

def get_cumulative_series(df: pd.DataFrame) -> dict:
    """
    Calcule la courbe cumulée du CA mois par mois multi-années.
    Utilisé pour le graphique 'Progression Cumulée'.
    """
    month_labels = ['Jan','Fév','Mar','Avr','Mai','Jun','Jul','Aoû','Sep','Oct','Nov','Déc']
    months = list(range(1, 13))

    if 'datetransaction' not in df.columns or df.empty:
        return {'labels': month_labels, 'ca': {}, 'marge': {}}

    years_in_data = sorted(df['datetransaction'].dt.year.dropna().unique().tolist(), reverse=True)
    years_to_process = years_in_data[:5]

    def cumul(df_yr, col):
        if df_yr.empty or col not in df_yr.columns:
            return [0.0] * 12
        grp = df_yr.groupby(df_yr['datetransaction'].dt.month)[col].sum()
        monthly = [float(grp.get(m, 0.0)) for m in months]
        # Running sum
        total = 0.0
        result = []
        for v in monthly:
            total += v
            result.append(round(total, 2))
        return result

    series = {
        'labels': month_labels,
        'ca': {},
        'marge': {}
    }

    for yr in years_to_process:
        yr_str = str(int(yr))
        df_yr = df[df['datetransaction'].dt.year == yr]
        series['ca'][yr_str] = cumul(df_yr, 'ca')
        series['marge'][yr_str] = cumul(df_yr, 'marge_ht')

    return series


# ─── Analyse du Spread (Achat HT vs Vente HT) ────────────────────────────────

def get_spread_analysis(df: pd.DataFrame) -> dict:
    """
    Agrégation mensuelle des moyennes de prix d'achat HT vs prix de vente HT.
    Retourne des listes par mois (1 à 12), incluant le spread pour N et N-1.
    """
    month_labels = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']
    months = list(range(1, 13))

    series = {
        'labels': month_labels,
        'gasoil': {'achat': [0]*12, 'vente': [0]*12, 'marge_n': [0]*12, 'marge_n1': [0]*12},
        'super': {'achat': [0]*12, 'vente': [0]*12, 'marge_n': [0]*12, 'marge_n1': [0]*12}
    }

    if 'datetransaction' not in df.columns or df.empty:
        return series

    df_n, df_n1, _, _ = _split_by_year(df)

    def get_monthly_avg(df_yr, col_name):
        if col_name not in df_yr.columns:
            return [0.0]*12
        df_valid = df_yr[df_yr[col_name] > 0]
        if df_valid.empty:
            return [0.0]*12
        grp = df_valid.groupby(df_valid['datetransaction'].dt.month)[col_name].mean()
        return [round(float(grp.get(m, 0.0)), 2) for m in months]

    # Vue classique (sans comparaison) utilise l'année N
    series['gasoil']['achat'] = get_monthly_avg(df_n, 'prix_achat_gasoil_ht')
    series['gasoil']['vente'] = get_monthly_avg(df_n, 'prix_vente_gasoil_ht')
    series['super']['achat'] = get_monthly_avg(df_n, 'prix_achat_super_ht')
    series['super']['vente'] = get_monthly_avg(df_n, 'prix_vente_super_ht')
    
    # Vue comparaison (Marge Unitaire = Vente - Achat)
    series['gasoil']['marge_n'] = [round(v - a, 2) if v > 0 and a > 0 else 0 for v, a in zip(series['gasoil']['vente'], series['gasoil']['achat'])]
    series['super']['marge_n'] = [round(v - a, 2) if v > 0 and a > 0 else 0 for v, a in zip(series['super']['vente'], series['super']['achat'])]
    
    # Marge unitaire N-1
    achat_go_n1 = get_monthly_avg(df_n1, 'prix_achat_gasoil_ht')
    vente_go_n1 = get_monthly_avg(df_n1, 'prix_vente_gasoil_ht')
    achat_sp_n1 = get_monthly_avg(df_n1, 'prix_achat_super_ht')
    vente_sp_n1 = get_monthly_avg(df_n1, 'prix_vente_super_ht')
    
    series['gasoil']['marge_n1'] = [round(v - a, 2) if v > 0 and a > 0 else 0 for v, a in zip(vente_go_n1, achat_go_n1)]
    series['super']['marge_n1'] = [round(v - a, 2) if v > 0 and a > 0 else 0 for v, a in zip(vente_sp_n1, achat_sp_n1)]

    return series


# ─── Rentabilité Client (Scatter Plot) ───────────────────────────────────────

def get_client_profitability(df: pd.DataFrame) -> list:
    """
    Agrégation par client : X = CA, Y = Marge HT.
    Retourne une liste d'objets pour le scatter plot (uniquement année N).
    """
    if 'client' not in df.columns or df.empty:
        return []

    df_n, _, _, _ = _split_by_year(df)
    
    if df_n.empty:
        return []

    agg_dict = {}
    if 'ca' in df_n.columns: agg_dict['ca'] = 'sum'
    if 'marge_ht' in df_n.columns: agg_dict['marge_ht'] = 'sum'
    if 'volume_gasoil' in df_n.columns: agg_dict['volume_gasoil'] = 'sum'
    if 'volume_super' in df_n.columns: agg_dict['volume_super'] = 'sum'

    if not agg_dict:
        return []

    grp = df_n.groupby('client').agg(agg_dict).reset_index()
    
    # Filtrer les valeurs négatives ou nulles
    grp = grp[(grp.get('ca', 0) > 0) & (grp.get('marge_ht', 0) > 0)]

    result = []
    for _, row in grp.iterrows():
        result.append({
            'name': str(row['client']),
            'data': [[
                round(float(row.get('ca', 0)), 2),
                round(float(row.get('marge_ht', 0)), 2)
            ]],
            'vol_total': round(float(row.get('volume_gasoil', 0)) + float(row.get('volume_super', 0)), 2)
        })
    return result


# ─── Scatter / Bubble Clients (Volume vs Marge) ───────────────────────────────

def get_client_bubble(df: pd.DataFrame) -> list:
    """
    Données pour le Bubble Chart :
    x = volume_gasoil, y = marge_ht, z = ca_total (taille bulle).
    Retourne les 20 premiers clients.
    """
    if 'client' not in df.columns or df.empty:
        return []

    agg_dict = {}
    if 'volume_gasoil' in df.columns: agg_dict['volume_gasoil'] = 'sum'
    if 'volume_super'  in df.columns: agg_dict['volume_super']  = 'sum'
    if 'marge_ht'      in df.columns: agg_dict['marge_ht']      = 'sum'
    if 'ca'      in df.columns: agg_dict['ca']      = 'sum'
    if not agg_dict:
        return []

    grp = df.groupby('client').agg(agg_dict).reset_index()

    # Trier par CA décroissant et prendre le top 20
    sort_col = 'ca' if 'ca' in grp.columns else grp.columns[1]
    grp = grp.nlargest(20, sort_col)

    result = []
    for _, row in grp.iterrows():
        vol_total = float(row.get('volume_gasoil', 0)) + float(row.get('volume_super', 0))
        result.append({
            'client': str(row['client']),
            'x': round(float(row.get('volume_gasoil', 0)), 2),
            'y': round(float(row.get('marge_ht', 0)), 2),
            'z': round(float(row.get('ca', 0)), 2),
            'vol_total': round(vol_total, 2),
            'vol_super': round(float(row.get('volume_super', 0)), 2),
        })
    return result


# ─── Heatmap Mensuelle (Activité par mois et année) ──────────────────────────

def get_monthly_heatmap(df: pd.DataFrame) -> list:
    """
    Données pour le Heatmap ApexCharts :
    Séries = [{name: 'CA', data: [{x: 'Jan', y: val}, ...]}]
    Pour chaque métrique disponible (CA, Gasoil, Super, Marge).
    Retourne les données structurées pour un heatmap multi-lignes.
    """
    if 'datetransaction' not in df.columns or df.empty:
        return []

    month_labels = ['Jan','Fév','Mar','Avr','Mai','Jun','Jul','Aoû','Sep','Oct','Nov','Déc']
    months = list(range(1, 13))

    years = sorted(df['datetransaction'].dt.year.dropna().unique().tolist(), reverse=True)[:3]
    series = []

    for yr in years:
        df_yr = df[df['datetransaction'].dt.year == int(yr)]
        col = 'ca' if 'ca' in df_yr.columns else (
              'volume_gasoil' if 'volume_gasoil' in df_yr.columns else None)
        if col is None:
            continue
        grp = df_yr.groupby(df_yr['datetransaction'].dt.month)[col].sum()
        data = [{'x': month_labels[m-1], 'y': round(float(grp.get(m, 0.0)), 2)} for m in months]
        series.append({'name': str(int(yr)), 'data': data})

    return series


# ─── Analyse Achats / Fournisseurs ───────────────────────────────────────────

def get_supplier_analysis(df: pd.DataFrame) -> dict:
    """
    Analyse complète côté achats, agrégée par fournisseur.

    Returns un dict :
      - kpis : indicateurs globaux achats
      - rows : scorecard par fournisseur (volume, coût d'achat, CA, marge, prix moyen…)
      - part_achat : répartition du coût d'achat par fournisseur (donut)
      - marge : marge HT par fournisseur (barres, triées)
      - price_evolution : évolution mensuelle du prix d'achat gasoil par top fournisseur
    """
    empty = {
        'kpis': {
            'nb_fournisseurs': 0, 'cout_achat_total': 0.0,
            'volume_achat_total': 0.0, 'marge_totale': 0.0,
            'prix_achat_moyen': 0.0, 'top_fournisseur': '—',
        },
        'rows': [], 'part_achat': {'labels': [], 'values': []},
        'marge': {'labels': [], 'values': []},
        'price_evolution': {'labels': [], 'series': []},
    }

    if 'fournisseur' not in df.columns or df.empty:
        return empty

    # On ignore les lignes sans fournisseur identifié pour l'analyse achats
    dff = df[~df['fournisseur'].isin(['NON RENSEIGNÉ', 'INCONNU', ''])].copy()
    if dff.empty:
        return empty

    agg = {}
    for col in ('volume_gasoil', 'volume_super', 'achat_ht', 'ca', 'marge_ht'):
        if col in dff.columns:
            agg[col] = 'sum'

    g = dff.groupby('fournisseur').agg(agg)
    g['nb_transactions'] = dff.groupby('fournisseur').size()
    g = g.reset_index()

    g['volume_total'] = g.get('volume_gasoil', 0) + g.get('volume_super', 0)
    g['taux_marge'] = np.where(g.get('ca', 0) > 0,
                               (g.get('marge_ht', 0) / g.get('ca', 1) * 100), 0.0)
    g['prix_achat_moyen'] = np.where(g['volume_total'] > 0,
                                     g.get('achat_ht', 0) / g['volume_total'], 0.0)

    g = g.sort_values('achat_ht', ascending=False) if 'achat_ht' in g.columns else g

    rows = []
    for _, r in g.iterrows():
        rows.append({
            'fournisseur': str(r['fournisseur']),
            'volume_gasoil': round(float(r.get('volume_gasoil', 0)), 2),
            'volume_super': round(float(r.get('volume_super', 0)), 2),
            'volume_total': round(float(r['volume_total']), 2),
            'cout_achat': round(float(r.get('achat_ht', 0)), 2),
            'ca': round(float(r.get('ca', 0)), 2),
            'marge': round(float(r.get('marge_ht', 0)), 2),
            'taux_marge': round(float(r['taux_marge']), 2),
            'prix_achat_moyen': round(float(r['prix_achat_moyen']), 4),
            'nb_transactions': int(r['nb_transactions']),
        })

    # ── KPIs globaux achats ──────────────────────────────────────────────────
    cout_total = float(g.get('achat_ht', pd.Series([0])).sum())
    vol_total = float(g['volume_total'].sum())
    marge_totale = float(g.get('marge_ht', pd.Series([0])).sum())
    kpis = {
        'nb_fournisseurs': int(g['fournisseur'].nunique()),
        'cout_achat_total': round(cout_total, 2),
        'volume_achat_total': round(vol_total, 2),
        'marge_totale': round(marge_totale, 2),
        'prix_achat_moyen': round(cout_total / vol_total, 4) if vol_total > 0 else 0.0,
        'top_fournisseur': rows[0]['fournisseur'] if rows else '—',
    }

    # ── Part d'achat (donut) : top 8 + Autres ────────────────────────────────
    part = g[['fournisseur', 'achat_ht']].copy() if 'achat_ht' in g.columns else pd.DataFrame()
    part_labels, part_values = [], []
    if not part.empty:
        part = part.sort_values('achat_ht', ascending=False)
        top = part.head(8)
        part_labels = [str(x) for x in top['fournisseur'].tolist()]
        part_values = [round(float(x), 2) for x in top['achat_ht'].tolist()]
        autres = float(part['achat_ht'].iloc[8:].sum())
        if autres > 0:
            part_labels.append('Autres')
            part_values.append(round(autres, 2))

    # ── Marge par fournisseur (barres triées) ────────────────────────────────
    marge_sorted = g[['fournisseur', 'marge_ht']].sort_values('marge_ht', ascending=False) \
        if 'marge_ht' in g.columns else pd.DataFrame()
    marge_block = {
        'labels': [str(x) for x in marge_sorted['fournisseur'].tolist()] if not marge_sorted.empty else [],
        'values': [round(float(x), 2) for x in marge_sorted['marge_ht'].tolist()] if not marge_sorted.empty else [],
    }

    # ── Évolution mensuelle du prix d'achat gasoil (top 4 fournisseurs) ───────
    price_evo = {'labels': [], 'series': []}
    if 'datetransaction' in dff.columns and 'prix_achat_gasoil_ht' in dff.columns:
        month_labels = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']
        months = list(range(1, 13))
        price_evo['labels'] = month_labels
        top4 = [r['fournisseur'] for r in rows[:4]]
        for fr in top4:
            sub = dff[(dff['fournisseur'] == fr) & (dff['prix_achat_gasoil_ht'] > 0)]
            if sub.empty:
                continue
            grp = sub.groupby(sub['datetransaction'].dt.month)['prix_achat_gasoil_ht'].mean()
            data = [round(float(grp.get(m, 0.0)), 2) if m in grp.index else None for m in months]
            price_evo['series'].append({'name': fr, 'data': data})

    return {
        'kpis': kpis,
        'rows': rows,
        'part_achat': {'labels': part_labels, 'values': part_values},
        'marge': marge_block,
        'price_evolution': price_evo,
    }


# ─── Suivi des Paiements (Créances clients & Dettes fournisseurs) ─────────────

def _build_party_rows(facture_map: dict, nb_map: dict, regle_map: dict,
                      solde_map: dict) -> list:
    """Construit les lignes par tiers : dû = facturé + solde initial − réglé."""
    tiers_all = set(facture_map) | set(regle_map) | set(solde_map)
    rows = []
    for t in tiers_all:
        facture = float(facture_map.get(t, 0.0))
        solde_init = float(solde_map.get(t, 0.0))
        regle = float(regle_map.get(t, 0.0))
        du_total = facture + solde_init
        reste = round(du_total - regle, 2)

        if reste <= 0.5:
            statut = 'Réglé'
        elif regle > 0 or solde_init != 0:
            statut = 'Partiel'
        else:
            statut = 'Impayé'

        pct = round(min(regle / du_total * 100, 100), 1) if du_total > 0 else (100.0 if reste <= 0 else 0.0)

        rows.append({
            'tiers': str(t),
            'facture': round(facture, 2),
            'solde_initial': round(solde_init, 2),
            'du_total': round(du_total, 2),
            'regle': round(regle, 2),
            'reste': reste,
            'pct': pct,
            'statut': statut,
            'nb_factures': int(nb_map.get(t, 0)),
        })

    # Tri : plus gros reste à régler en premier
    rows.sort(key=lambda r: r['reste'], reverse=True)
    return rows


def get_payments_overview(df_ventes: pd.DataFrame, df_achats: pd.DataFrame, paiements: pd.DataFrame, soldes: pd.DataFrame) -> dict:
    """
    Calcule l'état des créances (clients) et des dettes (fournisseurs).

    df        : transactions de vente (facturé via ca_total, acheté via achat_ht)
    paiements : DataFrame des règlements saisis (sens, tiers_type, tiers, montant)
    soldes    : DataFrame des soldes d'ouverture (tiers_type, tiers, montant)
    """
    # ── Montants facturés / achetés depuis les ventes ────────────────────────
    facture_client, nb_client = {}, {}
    if df_ventes is not None and not df_ventes.empty and 'client' in df_ventes.columns and 'ca' in df_ventes.columns:
        g = df_ventes.groupby('client')['ca'].sum()
        facture_client = {k: float(v) for k, v in g.items()}
        nb_client = {k: int(v) for k, v in df_ventes.groupby('client').size().items()}

    achat_four, nb_four = {}, {}
    if df_achats is not None and not df_achats.empty and 'fournisseur' in df_achats.columns and 'achat_ht' in df_achats.columns:
        dff = df_achats[~df_achats['fournisseur'].isin(['NON RENSEIGNÉ', 'INCONNU', ''])]
        g = dff.groupby('fournisseur')['achat_ht'].sum()
        achat_four = {k: float(v) for k, v in g.items()}
        nb_four = {k: int(v) for k, v in dff.groupby('fournisseur').size().items()}

    # ── Règlements saisis ────────────────────────────────────────────────────
    regle_client, regle_four = {}, {}
    if paiements is not None and not paiements.empty:
        enc = paiements[paiements['tiers_type'] == 'client']
        regle_client = {k: float(v) for k, v in enc.groupby('tiers')['montant'].sum().items()}
        pay = paiements[paiements['tiers_type'] == 'fournisseur']
        regle_four = {k: float(v) for k, v in pay.groupby('tiers')['montant'].sum().items()}

    # ── Soldes d'ouverture ───────────────────────────────────────────────────
    solde_client, solde_four = {}, {}
    if soldes is not None and not soldes.empty:
        sc = soldes[soldes['tiers_type'] == 'client']
        solde_client = {k: float(v) for k, v in sc.groupby('tiers')['montant'].sum().items()}
        sf = soldes[soldes['tiers_type'] == 'fournisseur']
        solde_four = {k: float(v) for k, v in sf.groupby('tiers')['montant'].sum().items()}

    clients = _build_party_rows(facture_client, nb_client, regle_client, solde_client)
    fournisseurs = _build_party_rows(achat_four, nb_four, regle_four, solde_four)

    total_a_encaisser = round(sum(r['reste'] for r in clients if r['reste'] > 0), 2)
    total_a_payer = round(sum(r['reste'] for r in fournisseurs if r['reste'] > 0), 2)

    kpis = {
        'total_a_encaisser': total_a_encaisser,
        'total_a_payer': total_a_payer,
        'solde_net': round(total_a_encaisser - total_a_payer, 2),
        'nb_clients_impayes': sum(1 for r in clients if r['statut'] != 'Réglé'),
        'nb_fournisseurs_impayes': sum(1 for r in fournisseurs if r['statut'] != 'Réglé'),
    }

    return {'kpis': kpis, 'clients': clients, 'fournisseurs': fournisseurs}


# ─── Résumé JSON pour le Chat ─────────────────────────────────────────────────

def get_data_summary_for_chat(df: pd.DataFrame, kpis: dict) -> dict:
    """
    Génère un résumé statistique léger du DataFrame pour le module Chat.
    Ce résumé est envoyé à Qwen pour répondre aux questions (sans calculs IA).

    Returns:
        Dict JSON sérialisable avec les données clés
    """
    summary = {
        'kpis_globaux': {
            'ca_total_mad': kpis.get('ca_total', 0),
            'ca_variation_pct_vs_n1': kpis.get('ca_variation'),
            'volume_gasoil_litres': kpis.get('volume_gasoil', 0),
            'volume_super_litres': kpis.get('volume_super', 0),
            'marge_ht_mad': kpis.get('marge_ht', 0),
            'taux_marge_pct': kpis.get('taux_marge', 0),
            'annee_courante': kpis.get('current_year'),
            'annee_precedente': kpis.get('previous_year'),
            'periode_debut': kpis.get('date_debut'),
            'periode_fin': kpis.get('date_fin'),
            'nb_transactions': kpis.get('total_transactions', 0),
            'nb_clients_distincts': kpis.get('nb_clients', 0),
            'nb_statuts': kpis.get('nb_statuts', 0),
        },
        'top5_clients_par_ca': [],
        'top5_statuts_par_marge': [],
        'repartition_produits': {},
    }

    # Top 5 clients
    if 'client' in df.columns and 'ca' in df.columns:
        top5_c = df.groupby('client')['ca'].sum().nlargest(5)
        summary['top5_clients_par_ca'] = [
            {'client': str(k), 'ca_mad': round(float(v), 2)}
            for k, v in top5_c.items()
        ]

    # Top 5 statuts
    if 'statut' in df.columns and 'marge_ht' in df.columns:
        top5_s = df.groupby('statut')['marge_ht'].sum().nlargest(5)
        summary['top5_statuts_par_marge'] = [
            {'statut': str(k), 'marge_mad': round(float(v), 2)}
            for k, v in top5_s.items()
        ]

    # Répartition produits
    vol_go = _safe_sum(df, 'volume_gasoil')
    vol_sp = _safe_sum(df, 'volume_super')
    total_vol = vol_go + vol_sp
    summary['repartition_produits'] = {
        'gasoil_litres': round(vol_go, 2),
        'gasoil_pct': round((vol_go / total_vol * 100), 1) if total_vol > 0 else 0,
        'super_sp_litres': round(vol_sp, 2),
        'super_sp_pct': round((vol_sp / total_vol * 100), 1) if total_vol > 0 else 0,
    }

    return summary


def prepare_activite_data(df: pd.DataFrame) -> dict:
    """Prépare les données pour le dashboard Activité (Ventes)."""
    if df is None or df.empty:
        return {"kpis": {}, "monthly_series": {}, "top10_clients": [], "margin_bridge": [], "product_mix": {}, "cumulative": {}, "client_bubble": [], "heatmap": {}, "spread": {}, "profitability": [], "filters_data": {"statuts": [], "clients": [], "date_min": "", "date_max": ""}}
    kpis = compute_kpis(df)
    monthly = get_monthly_series(df)
    top10 = get_top10_clients(df)
    bridge = get_margin_bridge(df)
    product_mix = get_product_mix(df)
    cumulative = get_cumulative_series(df)
    client_bubble = get_client_bubble(df)
    heatmap = get_monthly_heatmap(df)
    spread = get_spread_analysis(df)
    profitability = get_client_profitability(df)

    statuts = sorted(df['statut'].dropna().unique().tolist()) if 'statut' in df.columns else []
    clients = sorted(df['client'].dropna().unique().tolist()) if 'client' in df.columns else []
    
    years = []
    if 'datetransaction' in df.columns:
        years = sorted(df['datetransaction'].dt.year.dropna().unique().tolist(), reverse=True)

    date_min = str(df['datetransaction'].min().date()) if 'datetransaction' in df.columns else ''
    date_max = str(df['datetransaction'].max().date()) if 'datetransaction' in df.columns else ''

    return {
        'kpis': kpis,
        'monthly_series': monthly,
        'top10_clients': top10,
        'margin_bridge': bridge,
        'product_mix': product_mix,
        'cumulative': cumulative,
        'client_bubble': client_bubble,
        'heatmap': heatmap,
        'spread': spread,
        'profitability': profitability,
        'filters_data': {
            'statuts': [str(s) for s in statuts],
            'clients': [str(c) for c in clients],
            'years': [str(int(y)) for y in years],
            'date_min': date_min,
            'date_max': date_max,
        }
    }


def prepare_achats_data(df: pd.DataFrame) -> dict:
    """Prépare les données pour le dashboard Achats (Fournisseurs)."""
    df_n, df_n1, current_year, previous_year = _split_by_year(df)
    
    achat_n = _safe_sum(df_n, 'achat_ht')
    achat_n1 = _safe_sum(df_n1, 'achat_ht')
    
    vol_gasoil_n = _safe_sum(df_n, 'volume_gasoil')
    vol_gasoil_n1 = _safe_sum(df_n1, 'volume_gasoil')
    vol_super_n = _safe_sum(df_n, 'volume_super')
    vol_super_n1 = _safe_sum(df_n1, 'volume_super')
    vol_total_n = vol_gasoil_n + vol_super_n
    vol_total_n1 = vol_gasoil_n1 + vol_super_n1
    
    kpis = {
        'achat_ht': round(achat_n, 2),
        'achat_ht_n1': round(achat_n1, 2),
        'achat_variation': _calc_variation(achat_n, achat_n1),
        'volume_total': round(vol_total_n, 2),
        'volume_total_n1': round(vol_total_n1, 2),
        'vol_total_variation': _calc_variation(vol_total_n, vol_total_n1),
        'volume_gasoil': round(vol_gasoil_n, 2),
        'volume_gasoil_n1': round(vol_gasoil_n1, 2),
        'vol_gasoil_variation': _calc_variation(vol_gasoil_n, vol_gasoil_n1),
        'volume_super': round(vol_super_n, 2),
        'volume_super_n1': round(vol_super_n1, 2),
        'vol_super_variation': _calc_variation(vol_super_n, vol_super_n1),
        'current_year': current_year,
        'previous_year': previous_year
    }
    
    supplier_analysis = get_supplier_analysis(df)
    product_mix = get_product_mix(df)
    monthly = get_monthly_series(df)
    
    statuts = sorted(df['statut'].dropna().unique().tolist()) if 'statut' in df.columns else []
    fournisseurs = sorted(df['fournisseur'].dropna().unique().tolist()) if 'fournisseur' in df.columns else []
    
    years = []
    if 'datetransaction' in df.columns:
        years = sorted(df['datetransaction'].dt.year.dropna().unique().tolist(), reverse=True)

    date_min = str(df['datetransaction'].min().date()) if 'datetransaction' in df.columns else ''
    date_max = str(df['datetransaction'].max().date()) if 'datetransaction' in df.columns else ''

    return {
        'kpis': kpis,
        'supplier_analysis': supplier_analysis,
        'product_mix': product_mix,
        'monthly_series': monthly,
        'filters_data': {
            'statuts': [str(s) for s in statuts],
            'fournisseurs': [str(f) for f in fournisseurs],
            'years': [str(int(y)) for y in years],
            'date_min': date_min,
            'date_max': date_max,
        }
    }
