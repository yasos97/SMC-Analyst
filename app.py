"""
SalamaIQ — Application Flask Principale
=========================================
Routes :
  GET  /            → Page d'accueil / upload
  POST /upload      → Pipeline complet de traitement
  POST /api/chat    → Module Chat IA (Qwen #3)
  GET  /api/filtered-data → Données filtrées pour mise à jour dynamique des graphiques
  GET  /api/filters → Liste des fournisseurs et clients disponibles
"""

import os
import json
import pickle
import uuid
import tempfile
from datetime import datetime

import numpy as np
import pandas as pd
from flask import (Flask, render_template, request, jsonify,
                   session, redirect, url_for)
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

# ── Base de Données ──────────────────────────────────────────────────────────
from database.models import db, init_db, load_all_transactions, clear_database, Transaction

# ── Modules SalamaIQ ─────────────────────────────────────────────────────────
from processing.ingestion import read_file
from processing.ai_mapper import map_columns, generate_executive_summary, answer_chat_question
from processing.normalizer import normalize_dataframe
from processing.calculator import (
    compute_kpis, get_monthly_series,
    get_top10_clients, get_margin_bridge,
    get_data_summary_for_chat,
    get_product_mix, get_cumulative_series,
    get_client_bubble, get_monthly_heatmap
)

# ─── Configuration ────────────────────────────────────────────────────────────

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(32))
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 Mo max
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///salama_iq.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

init_db(app)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv', 'xlsm'}

# ── Plus de DATA_STORE en mémoire, tout repose sur SQLite ───────────────



# ─── Encodeur JSON personnalisé (gère numpy types) ────────────────────────────

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (pd.Timestamp, datetime)):
            return str(obj)
        if obj is None or (isinstance(obj, float) and np.isnan(obj)):
            return None
        return super().default(obj)


def jsonify_safe(data: dict):
    """Sérialise en JSON en gérant les types numpy/pandas."""
    return app.response_class(
        response=json.dumps(data, cls=NumpyEncoder, ensure_ascii=False),
        status=200,
        mimetype='application/json'
    )


# ─── Utilitaires ─────────────────────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_session_id() -> str:
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']


def get_dataframe(session_id: str) -> pd.DataFrame | None:
    df = load_all_transactions()
    return df if not df.empty else None


def store_dataframe(session_id: str, df: pd.DataFrame):
    """Insère un DataFrame filtré dans la base SQLite."""
    cols_to_keep = ['datetransaction', 'client', 'fournisseur', 'produit', 
                    'volume_gasoil', 'volume_super', 'ca_total', 'marge_ht']
    cols_available = [c for c in cols_to_keep if c in df.columns]
    
    df_db = df[cols_available].copy()
    if 'datetransaction' in df_db.columns:
        df_db['datetransaction'] = pd.to_datetime(df_db['datetransaction'])
        
    df_db['batch_id'] = str(uuid.uuid4())
    
    # Enregistrer en base
    df_db.to_sql('transaction', db.engine, if_exists='append', index=False)


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Applique les filtres utilisateur au DataFrame."""
    df_filtered = df.copy()

    if filters.get('date_from'):
        try:
            df_filtered = df_filtered[
                df_filtered['datetransaction'] >= pd.to_datetime(filters['date_from'])
            ]
        except Exception:
            pass

    if filters.get('date_to'):
        try:
            df_filtered = df_filtered[
                df_filtered['datetransaction'] <= pd.to_datetime(filters['date_to'])
            ]
        except Exception:
            pass

    if filters.get('fournisseur') and 'fournisseur' in df_filtered.columns:
        fournisseurs = filters['fournisseur'] if isinstance(filters['fournisseur'], list) else [filters['fournisseur']]
        if fournisseurs and fournisseurs != ['']:
            df_filtered = df_filtered[df_filtered['fournisseur'].isin(fournisseurs)]

    if filters.get('client') and 'client' in df_filtered.columns:
        clients = filters['client'] if isinstance(filters['client'], list) else [filters['client']]
        if clients and clients != ['']:
            df_filtered = df_filtered[df_filtered['client'].isin(clients)]

    return df_filtered


def prepare_dashboard_data(df: pd.DataFrame) -> dict:
    """Prépare toutes les données nécessaires au template dashboard."""
    kpis = compute_kpis(df)
    monthly = get_monthly_series(df)
    top10 = get_top10_clients(df)
    bridge = get_margin_bridge(df)
    product_mix = get_product_mix(df)
    cumulative = get_cumulative_series(df)
    client_bubble = get_client_bubble(df)
    heatmap = get_monthly_heatmap(df)

    # Listes pour les filtres
    fournisseurs = sorted(df['fournisseur'].dropna().unique().tolist()) if 'fournisseur' in df.columns else []
    clients = sorted(df['client'].dropna().unique().tolist()) if 'client' in df.columns else []

    # Dates min/max pour le date picker
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
        'filters_data': {
            'fournisseurs': [str(f) for f in fournisseurs],
            'clients': [str(c) for c in clients],
            'date_min': date_min,
            'date_max': date_max,
        }
    }


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    """Page principale unifiée : charge le Dashboard depuis la BDD ou affiche l'état vide."""
    session_id = get_session_id()
    df = get_dataframe(session_id)

    # Si aucune donnée en BDD → état vide (on passe db_empty=True au template)
    if df is None or df.empty:
        empty_kpis = {
            'ca_total': 0, 'ca_total_n1': 0, 'ca_variation': None,
            'volume_gasoil': 0, 'volume_gasoil_n1': 0, 'vol_gasoil_variation': None,
            'volume_super': 0, 'volume_super_n1': 0, 'vol_super_variation': None,
            'marge_ht': 0, 'marge_ht_n1': 0, 'marge_variation': None,
            'taux_marge': 0, 'taux_marge_n1': 0,
            'current_year': 0, 'previous_year': 0,
            'date_debut': '—', 'date_fin': '—',
            'total_transactions': 0, 'nb_clients': 0, 'nb_fournisseurs': 0,
            'ca_month': 0, 'ca_prev_month': 0, 'ca_month_variation': None, 'month_label': '—',
        }
        return render_template('dashboard.html',
            session_id=session_id,
            filename="Aucune donnée",
            mapping_source="—",
            column_mapping={},
            kpis=empty_kpis,
            monthly_series=json.dumps({}),
            top10_clients=json.dumps([]),
            margin_bridge=json.dumps([]),
            product_mix=json.dumps({}),
            cumulative=json.dumps({}),
            client_bubble=json.dumps([]),
            heatmap=json.dumps({}),
            filters_data=json.dumps({'fournisseurs': [], 'clients': [], 'date_min': '', 'date_max': ''}),
            diagnostic="",
            nb_rows=0,
            columns_found=[],
            red_flags=[],
            db_empty=True,
        )

    # Données existantes → Dashboard complet
    dashboard_data = prepare_dashboard_data(df)
    return render_template('dashboard.html',
        session_id=session_id,
        filename=f"Historique ({len(df)} transactions)",
        mapping_source="BDD SQLite",
        column_mapping={},
        kpis=dashboard_data['kpis'],
        monthly_series=json.dumps(dashboard_data['monthly_series'], cls=NumpyEncoder),
        top10_clients=json.dumps(dashboard_data['top10_clients'], cls=NumpyEncoder),
        margin_bridge=json.dumps(dashboard_data['margin_bridge'], cls=NumpyEncoder),
        product_mix=json.dumps(dashboard_data['product_mix'], cls=NumpyEncoder),
        cumulative=json.dumps(dashboard_data['cumulative'], cls=NumpyEncoder),
        client_bubble=json.dumps(dashboard_data['client_bubble'], cls=NumpyEncoder),
        heatmap=json.dumps(dashboard_data['heatmap'], cls=NumpyEncoder),
        filters_data=json.dumps(dashboard_data['filters_data'], cls=NumpyEncoder),
        diagnostic="",
        nb_rows=len(df),
        columns_found=[],
        red_flags=[],
        db_empty=False,
    )


@app.route('/upload', methods=['POST'])
def upload():
    """
    Pipeline complet de traitement :
    1. Lecture du fichier
    2. Mapping IA des colonnes (Qwen #1)
    3. Normalisation Pandas
    4. Calcul des KPIs
    5. Diagnostic IA (Qwen #2)
    6. Rendu du dashboard
    """
    # ── Validation du fichier uploadé ────────────────────────────────────────
    if 'files' not in request.files:
        if 'file' in request.files:  # Fallback si ancien input
            files = request.files.getlist('file')
        else:
            return render_template('index.html', error="Aucun fichier sélectionné.")
    else:
        files = request.files.getlist('files')

    if not files or all(f.filename == '' for f in files):
        return render_template('index.html', error="Fichiers invalides.")

    dfs_to_concat = []
    final_mapping = {}
    filenames = []
    mapping_source = "IA (Qwen)"

    for file in files:
        if not allowed_file(file.filename):
            continue

        filename_sec = secure_filename(file.filename)
        filenames.append(filename_sec)
        filepath = os.path.join(UPLOAD_FOLDER, filename_sec)

        try:
            file.save(filepath)
            # ── Étape 1 : Ingestion ───────────────────────────────────────────────
            df_raw, raw_headers = read_file(filepath)
            if df_raw.empty:
                continue

            # ── Étape 2 : Mapping IA (Qwen #1) ───────────────────────────────────
            try:
                ai_mapping = map_columns(raw_headers)
                if not ai_mapping:
                    mapping_source = "Heuristique"
            except Exception as e:
                print(f"[SalamaIQ] Mapping IA indisponible: {e}")
                ai_mapping = {}
                mapping_source = "Heuristique"

            # ── Étape 3 : Normalisation (Pandas) ─────────────────────────────────
            df_norm, mapping = normalize_dataframe(df_raw, ai_mapping)
            if not df_norm.empty:
                dfs_to_concat.append(df_norm)
                final_mapping.update(mapping)

        except Exception as e:
            print(f"Erreur lors du traitement de {filename_sec} : {e}")
        finally:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception:
                pass

    if not dfs_to_concat:
        return render_template('index.html', error="Aucune donnée valide n'a pu être extraite des fichiers fournis.")

    # ── Fusion Finale ────────────────────────────────────────────────────────
    df_clean = pd.concat(dfs_to_concat, ignore_index=True)
    
    # ── Étape Qualité des Données (Red Flags) ────────────────────────────────
    red_flags = []
    if len(dfs_to_concat) > 1:
        red_flags.append(f"📦 {len(dfs_to_concat)} fichiers fusionnés avec succès (Total : {len(df_clean)} transactions).")

    # Marge manquante
    if 'marge_ht' in df_clean.columns:
        marge_nulls = df_clean['marge_ht'].isna().sum()
        pct_marge_miss = (marge_nulls / len(df_clean)) * 100
        if pct_marge_miss > 5:
            red_flags.append(f"⚠️ {pct_marge_miss:.1f}% des transactions n'ont pas de marge HT renseignée.")
            
    # Volume gasoil manquant
    if 'volume_gasoil' in df_clean.columns:
        go_nulls = df_clean['volume_gasoil'].isna().sum()
        if (go_nulls / len(df_clean)) > 0.8:
            red_flags.append("⚠️ Alerte : Très peu de Gasoil détecté dans le(s) fichier(s).")

    # ── Stockage en Base de Données (SQLite) ─────────────────────────────────
    session_id = get_session_id()
    store_dataframe(session_id, df_clean)

    # ── Rechargement Complet (Passé + Présent) ───────────────────────────────
    df_history = get_dataframe(session_id)

    # ── Étape 4 : Calcul des KPIs (Pandas sur tout l'historique) ─────────────
    dashboard_data = prepare_dashboard_data(df_history)
    kpis = dashboard_data['kpis']
    filename_display = f"Données Globales ({len(filenames)} nv. fichiers aj.)"

    # ── Étape 5 : Diagnostic IA (Qwen #2) ────────────────────────────────────
    diagnostic = "Analyse IA en cours..."
    try:
        diagnostic = generate_executive_summary(kpis)
    except Exception as e:
        print(f"[SalamaIQ] Diagnostic IA indisponible: {e}")
        diagnostic = (
            "• **Données chargées avec succès** : Les KPIs et graphiques sont prêts.\n"
            "• **Analyse IA temporairement indisponible** : Réessayez dans quelques instants.\n"
            "• **Données fiables** : Tous les calculs sont effectués par le moteur Pandas."
        )

    # ── Rendu du Dashboard ────────────────────────────────────────────────────
    return render_template(
        'dashboard.html',
        session_id=session_id,
        filename=filename_display,
        mapping_source=mapping_source,
        column_mapping=final_mapping,
        kpis=dashboard_data['kpis'],
        monthly_series=json.dumps(dashboard_data['monthly_series'], cls=NumpyEncoder),
        top10_clients=json.dumps(dashboard_data['top10_clients'], cls=NumpyEncoder),
        margin_bridge=json.dumps(dashboard_data['margin_bridge'], cls=NumpyEncoder),
        product_mix=json.dumps(dashboard_data['product_mix'], cls=NumpyEncoder),
        cumulative=json.dumps(dashboard_data['cumulative'], cls=NumpyEncoder),
        client_bubble=json.dumps(dashboard_data['client_bubble'], cls=NumpyEncoder),
        heatmap=json.dumps(dashboard_data['heatmap'], cls=NumpyEncoder),
        filters_data=json.dumps(dashboard_data['filters_data'], cls=NumpyEncoder),
        diagnostic=diagnostic,
        nb_rows=len(df_history),
        columns_found=list(final_mapping.values()),
        red_flags=red_flags,
    )


@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Module Chat IA (Qwen #3).
    Reçoit une question, génère un résumé Pandas, interroge Qwen.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Requête invalide'}), 400

        question = data.get('question', '').strip()
        session_id = data.get('session_id', get_session_id())

        if not question:
            return jsonify({'error': 'Question vide'}), 400

        # Récupérer le DataFrame
        df = get_dataframe(session_id)
        if df is None or df.empty:
            return jsonify({
                'answer': "Aucune donnée chargée. Veuillez d'abord uploader un fichier."
            })

        # Générer le résumé Pandas (le seul moteur mathématique)
        kpis = compute_kpis(df)
        data_summary = get_data_summary_for_chat(df, kpis)

        # Interroger Qwen avec le résumé JSON
        answer = answer_chat_question(data_summary, question)

        return jsonify({'answer': answer, 'status': 'ok'})

    except Exception as e:
        return jsonify({'answer': f"Erreur : {str(e)}", 'status': 'error'}), 500


@app.route('/api/filtered-data', methods=['GET'])
def filtered_data():
    """
    Retourne les données recalculées après application des filtres.
    Utilisé pour la mise à jour dynamique des graphiques sans rechargement de page.
    """
    try:
        session_id = request.args.get('session_id', get_session_id())
        df = get_dataframe(session_id)

        if df is None or df.empty:
            return jsonify({'error': 'Aucune donnée disponible'}), 404

        # Appliquer les filtres
        filters = {
            'date_from': request.args.get('date_from'),
            'date_to': request.args.get('date_to'),
            'fournisseur': request.args.getlist('fournisseur'),
            'client': request.args.getlist('client'),
        }
        df_filtered = apply_filters(df, filters)

        if df_filtered.empty:
            return jsonify({'error': 'Aucune donnée pour ces filtres'}), 200

        # Recalculer les données
        dashboard_data = prepare_dashboard_data(df_filtered)

        return jsonify_safe({
            'kpis': dashboard_data['kpis'],
            'monthly_series': dashboard_data['monthly_series'],
            'top10_clients': dashboard_data['top10_clients'],
            'margin_bridge': dashboard_data['margin_bridge'],
            'nb_rows': len(df_filtered),
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    """Retourne les transactions brutes pour la grille DataTables (Drill-down)"""
    try:
        session_id = request.args.get('session_id', get_session_id())
        df = get_dataframe(session_id)
        if df is None or df.empty:
            return jsonify({'data': []})
            
        # On limite aux 5000 dernières lignes pour la perf
        df_view = df.sort_values(by='datetransaction', ascending=False) if 'datetransaction' in df.columns else df.copy()
        df_view = df_view.head(5000)
        
        # Convertir les dates
        if 'datetransaction' in df_view.columns:
            # Format MM/JJ/AAAA cohérent avec le fichier Excel source
            df_view['datetransaction'] = df_view['datetransaction'].dt.strftime('%m/%d/%Y')
            
        df_view = df_view.fillna('')
        for col in ['ca_total', 'volume_gasoil', 'volume_super', 'marge_ht']:
            if col in df_view.columns:
                df_view[col] = pd.to_numeric(df_view[col], errors='coerce').fillna(0).round(2)

        # Inclure l'ID de la ligne pour les opérations CRUD
        if 'id' not in df_view.columns:
            df_view['id'] = range(1, len(df_view) + 1)

        return jsonify_safe({'data': df_view.to_dict(orient='records')})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/filters', methods=['GET'])
def get_filters():
    """Retourne les listes de fournisseurs et clients disponibles."""
    try:
        session_id = request.args.get('session_id', get_session_id())
        df = get_dataframe(session_id)

        if df is None:
            return jsonify({'fournisseurs': [], 'clients': []})

        return jsonify({
            'fournisseurs': sorted(df['fournisseur'].dropna().unique().tolist()) if 'fournisseur' in df.columns else [],
            'clients': sorted(df['client'].dropna().unique().tolist()) if 'client' in df.columns else [],
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/purge', methods=['POST'])
def api_purge():
    try:
        clear_database()
        return jsonify({'status': 'success', 'message': 'Historique purgé avec succès.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500



# ─── Routes BDD Manager (CRUD) ───────────────────────────────────────────────

@app.route('/api/transactions/add', methods=['POST'])
def add_transaction():
    """Ajoute une transaction manuellement."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Données manquantes'}), 400

        tx = Transaction(
            batch_id='manual',
            datetransaction=pd.to_datetime(data.get('datetransaction')) if data.get('datetransaction') else None,
            client=data.get('client', ''),
            fournisseur=data.get('fournisseur', ''),
            produit=data.get('produit', ''),
            volume_gasoil=float(data.get('volume_gasoil', 0) or 0),
            volume_super=float(data.get('volume_super', 0) or 0),
            ca_total=float(data.get('ca_total', 0) or 0),
            marge_ht=float(data.get('marge_ht', 0) or 0),
        )
        db.session.add(tx)
        db.session.commit()
        return jsonify({'status': 'success', 'id': tx.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/transactions/<int:tx_id>/update', methods=['PUT'])
def update_transaction(tx_id):
    """Met à jour une transaction existante."""
    try:
        data = request.get_json()
        tx = db.session.get(Transaction, tx_id)
        if not tx:
            return jsonify({'error': 'Transaction introuvable'}), 404

        if data.get('datetransaction'):
            tx.datetransaction = pd.to_datetime(data['datetransaction'])
        tx.client = data.get('client', tx.client)
        tx.fournisseur = data.get('fournisseur', tx.fournisseur)
        tx.produit = data.get('produit', tx.produit)
        tx.volume_gasoil = float(data.get('volume_gasoil', tx.volume_gasoil) or 0)
        tx.volume_super = float(data.get('volume_super', tx.volume_super) or 0)
        tx.ca_total = float(data.get('ca_total', tx.ca_total) or 0)
        tx.marge_ht = float(data.get('marge_ht', tx.marge_ht) or 0)

        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/transactions/<int:tx_id>/delete', methods=['DELETE'])
def delete_transaction(tx_id):
    """Supprime une transaction."""
    try:
        tx = db.session.get(Transaction, tx_id)
        if not tx:
            return jsonify({'error': 'Transaction introuvable'}), 404
        db.session.delete(tx)
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ─── Point d'entrée ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("=" * 55)
    print("  SalamaIQ -- SMC Salama Analytics Engine")
    print("  Version 1.0 | Powered by Pandas + Qwen 3.5")
    print("  Dashboard : http://127.0.0.1:5000")
    print("=" * 55)
    app.run(debug=True, port=5000, host='0.0.0.0')
