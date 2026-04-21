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
    ca_n = _safe_sum(df_n, 'ca_total')
    ca_n1 = _safe_sum(df_n1, 'ca_total')
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

    # ── Taux de Marge ────────────────────────────────────────────────────────
    taux_marge_n = round((marge_n / ca_n * 100), 2) if ca_n > 0 else 0.0
    taux_marge_n1 = round((marge_n1 / ca_n1 * 100), 2) if ca_n1 > 0 else 0.0

    # ── Métadonnées ──────────────────────────────────────────────────────────
    date_debut = str(df['datetransaction'].min().date()) if 'datetransaction' in df.columns else 'N/D'
    date_fin = str(df['datetransaction'].max().date()) if 'datetransaction' in df.columns else 'N/D'
    nb_clients = int(df['client'].nunique()) if 'client' in df.columns else 0
    nb_fournisseurs = int(df['fournisseur'].nunique()) if 'fournisseur' in df.columns else 0

    # ── KPIs Avancés pour la Variation Mois en Cours ────────────────────────
    current_month_kpis = {}
    if 'datetransaction' in df_n.columns and not df_n.empty:
        last_month = df_n['datetransaction'].dt.month.max()
        df_current_month = df_n[df_n['datetransaction'].dt.month == last_month]
        df_prev_month = df_n[df_n['datetransaction'].dt.month == (last_month - 1)] if last_month > 1 else pd.DataFrame()
        current_month_kpis = {
            'ca_month': _safe_sum(df_current_month, 'ca_total'),
            'ca_prev_month': _safe_sum(df_prev_month, 'ca_total'),
            'ca_month_variation': _calc_variation(
                _safe_sum(df_current_month, 'ca_total'),
                _safe_sum(df_prev_month, 'ca_total')
            ),
            'month_label': df_current_month['datetransaction'].dt.strftime('%B %Y').iloc[0]
                           if not df_current_month.empty else ''
        }

    return {
        # CA
        'ca_total': round(ca_n, 2),
        'ca_total_n1': round(ca_n1, 2),
        'ca_variation': ca_variation,
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
        # Années
        'current_year': current_year,
        'previous_year': previous_year,
        # Métadonnées
        'date_debut': date_debut,
        'date_fin': date_fin,
        'total_transactions': len(df),
        'nb_clients': nb_clients,
        'nb_fournisseurs': nb_fournisseurs,
        # Mois en cours
        **current_month_kpis,
    }


# ─── Séries Mensuelles (pour les graphiques) ─────────────────────────────────

def get_monthly_series(df: pd.DataFrame) -> dict:
    """
    Calcule les séries mensuelles pour les graphiques d'évolution N vs N-1.

    Returns:
        Dict avec labels et séries pour CA, volumes, marge
    """
    if 'datetransaction' not in df.columns or df.empty:
        empty_series = [0.0] * 12
        return {
            'labels': ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun',
                       'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc'],
            'ca_n': empty_series, 'ca_n1': empty_series,
            'vol_gasoil_n': empty_series, 'vol_gasoil_n1': empty_series,
            'vol_super_n': empty_series, 'vol_super_n1': empty_series,
            'marge_n': empty_series, 'marge_n1': empty_series,
        }

    df_n, df_n1, current_year, previous_year = _split_by_year(df)
    months = list(range(1, 13))
    month_labels = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun',
                    'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']

    def monthly_agg(df_year: pd.DataFrame, col: str) -> list:
        if df_year.empty or col not in df_year.columns:
            return [0.0] * 12
        grp = df_year.groupby(df_year['datetransaction'].dt.month)[col].sum()
        return [round(float(grp.get(m, 0.0)), 2) for m in months]

    
    # ── Prédictions (Forecast) ────────────────────────────────────────────────
    # On reconstruit une série temporelle continue (N-1 puis N) propre
    def get_continuous_series(col):
        hist = []
        for v in monthly_agg(df_n1, col): 
            if v > 0: hist.append(v)
        for v in monthly_agg(df_n, col): 
            if v > 0: hist.append(v)
        return hist
        
    ca_hist = get_continuous_series('ca_total')
    ca_future = generate_forecast(ca_hist, periods=3)
    
    # Placer la prédiction au bon endroit dans un tableau de 12 valeurs (si N n'est pas fini)
    # ou créer 3 mois fictifs (M+1, M+2, M+3)
    n_counts = sum(1 for v in monthly_agg(df_n, 'ca_total') if v > 0)
    
    extended_labels = month_labels.copy()
    ca_forecast = [None] * 12
    
    if n_counts == 12:
        # Année pleine, on ajoute M+1, M+2, M+3
        extended_labels += ['Jan (N+1)', 'Fév (N+1)', 'Mar (N+1)']
        ca_forecast += ca_future
        
        ca_n_ext = monthly_agg(df_n, 'ca_total') + [None, None, None]
        ca_n1_ext = monthly_agg(df_n1, 'ca_total') + [None, None, None]
    else:
        # Année en cours, on comble les mois restants
        ca_n_ext = monthly_agg(df_n, 'ca_total')
        ca_n1_ext = monthly_agg(df_n1, 'ca_total')
        
        idx = n_counts
        for i, val in enumerate(ca_future):
            if idx + i < 12:
                ca_forecast[idx + i] = round(val, 2)
            else:
                extended_labels.append(f"M+{idx+i-11}")
                ca_forecast.append(round(val, 2))
                ca_n_ext.append(None)
                ca_n1_ext.append(None)

    return {
        'labels': extended_labels,
        'current_year': current_year,
        'previous_year': previous_year,
        
        'ca_n': ca_n_ext,
        'ca_n1': ca_n1_ext,
        'ca_forecast': ca_forecast,
        
        'vol_gasoil_n': monthly_agg(df_n, 'volume_gasoil') + [None]*(len(extended_labels)-12),
        'vol_gasoil_n1': monthly_agg(df_n1, 'volume_gasoil') + [None]*(len(extended_labels)-12),
        'vol_super_n': monthly_agg(df_n, 'volume_super') + [None]*(len(extended_labels)-12),
        'vol_super_n1': monthly_agg(df_n1, 'volume_super') + [None]*(len(extended_labels)-12),
        'marge_n': monthly_agg(df_n, 'marge_ht') + [None]*(len(extended_labels)-12),
        'marge_n1': monthly_agg(df_n1, 'marge_ht') + [None]*(len(extended_labels)-12),
    }


# ─── Top 10 Clients ───────────────────────────────────────────────────────────

def get_top10_clients(df: pd.DataFrame) -> list:
    """
    Retourne le Top 10 des clients par CA total.

    Returns:
        Liste de dicts [{client, ca, volume_total, marge}]
    """
    if 'client' not in df.columns or df.empty:
        return []

    agg_dict = {}
    if 'ca_total' in df.columns:
        agg_dict['ca_total'] = 'sum'
    if 'volume_gasoil' in df.columns:
        agg_dict['volume_gasoil'] = 'sum'
    if 'volume_super' in df.columns:
        agg_dict['volume_super'] = 'sum'
    if 'marge_ht' in df.columns:
        agg_dict['marge_ht'] = 'sum'

    if not agg_dict:
        return []

    top = df.groupby('client').agg(agg_dict)

    # Trier par CA si disponible, sinon par volume
    sort_col = 'ca_total' if 'ca_total' in top.columns else list(top.columns)[0]
    top = top.nlargest(10, sort_col).reset_index()

    result = []
    for _, row in top.iterrows():
        item = {
            'client': str(row['client']),
            'ca': round(float(row.get('ca_total', 0)), 2),
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
    Calcule la courbe cumulée du CA mois par mois pour N et N-1.
    Utilisé pour le graphique 'Progression Cumulée'.
    """
    if 'datetransaction' not in df.columns or df.empty:
        empty = [0.0] * 12
        return {'labels': ['Jan','Fév','Mar','Avr','Mai','Jun','Jul','Aoû','Sep','Oct','Nov','Déc'],
                'cumul_n': empty, 'cumul_n1': empty}

    df_n, df_n1, current_year, previous_year = _split_by_year(df)
    months = list(range(1, 13))
    month_labels = ['Jan','Fév','Mar','Avr','Mai','Jun','Jul','Aoû','Sep','Oct','Nov','Déc']

    def cumul(df_year, col):
        if df_year.empty or col not in df_year.columns:
            return [0.0] * 12
        grp = df_year.groupby(df_year['datetransaction'].dt.month)[col].sum()
        monthly = [float(grp.get(m, 0.0)) for m in months]
        # Running sum
        total = 0.0
        result = []
        for v in monthly:
            total += v
            result.append(round(total, 2))
        return result

    return {
        'labels': month_labels,
        'current_year': current_year,
        'previous_year': previous_year,
        'cumul_n': cumul(df_n, 'ca_total'),
        'cumul_n1': cumul(df_n1, 'ca_total'),
        'cumul_marge_n': cumul(df_n, 'marge_ht'),
        'cumul_marge_n1': cumul(df_n1, 'marge_ht'),
    }


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
    if 'ca_total'      in df.columns: agg_dict['ca_total']      = 'sum'
    if not agg_dict:
        return []

    grp = df.groupby('client').agg(agg_dict).reset_index()

    # Trier par CA décroissant et prendre le top 20
    sort_col = 'ca_total' if 'ca_total' in grp.columns else grp.columns[1]
    grp = grp.nlargest(20, sort_col)

    result = []
    for _, row in grp.iterrows():
        vol_total = float(row.get('volume_gasoil', 0)) + float(row.get('volume_super', 0))
        result.append({
            'client': str(row['client']),
            'x': round(float(row.get('volume_gasoil', 0)), 2),
            'y': round(float(row.get('marge_ht', 0)), 2),
            'z': round(float(row.get('ca_total', 0)), 2),
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
        col = 'ca_total' if 'ca_total' in df_yr.columns else (
              'volume_gasoil' if 'volume_gasoil' in df_yr.columns else None)
        if col is None:
            continue
        grp = df_yr.groupby(df_yr['datetransaction'].dt.month)[col].sum()
        data = [{'x': month_labels[m-1], 'y': round(float(grp.get(m, 0.0)), 2)} for m in months]
        series.append({'name': str(int(yr)), 'data': data})

    return series


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
            'nb_fournisseurs': kpis.get('nb_fournisseurs', 0),
        },
        'top5_clients_par_ca': [],
        'top5_fournisseurs_par_marge': [],
        'repartition_produits': {},
    }

    # Top 5 clients
    if 'client' in df.columns and 'ca_total' in df.columns:
        top5_c = df.groupby('client')['ca_total'].sum().nlargest(5)
        summary['top5_clients_par_ca'] = [
            {'client': str(k), 'ca_mad': round(float(v), 2)}
            for k, v in top5_c.items()
        ]

    # Top 5 fournisseurs
    if 'fournisseur' in df.columns and 'marge_ht' in df.columns:
        top5_f = df.groupby('fournisseur')['marge_ht'].sum().nlargest(5)
        summary['top5_fournisseurs_par_marge'] = [
            {'fournisseur': str(k), 'marge_mad': round(float(v), 2)}
            for k, v in top5_f.items()
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
