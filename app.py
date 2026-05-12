"""
SalamaIQ — Application Flask Principale
=========================================
Routes :
  GET  /            → Page d'accueil / upload
  POST /upload      → Pipeline complet de traitement
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
                   session, redirect, url_for, send_file, Response)
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from functools import wraps
import pyotp
import qrcode
import base64
import io

# ── Base de Données ──────────────────────────────────────────────────────────
from database.models import db, init_db, load_all_transactions, clear_database, Transaction

# ── Modules SalamaIQ ─────────────────────────────────────────────────────────
from processing.pdf_generator import generate_client_report
from processing.ingestion import read_file
from processing.normalizer import normalize_dataframe
from processing.calculator import (
    compute_kpis, get_monthly_series,
    get_top10_clients, get_margin_bridge,
    get_product_mix, get_cumulative_series,
    get_client_bubble, get_monthly_heatmap,
    get_spread_analysis, get_client_profitability
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


# ─── Sécurité & Authentification ──────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Gestionnaire de connexion : Mot de passe + 2FA."""
    # Config depuis .env ou défaut
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'salama2026')
    TOTP_SECRET = os.getenv('TOTP_SECRET')
    
    # Si pas de secret TOTP dans .env, on en génère un persistant pour la session
    if not TOTP_SECRET:
        if 'temp_totp_secret' not in session:
            session['temp_totp_secret'] = pyotp.random_base32()
        TOTP_SECRET = session['temp_totp_secret']

    totp = pyotp.TOTP(TOTP_SECRET)

    if request.method == 'POST':
        # Étape 1 : Mot de passe
        if 'password' in request.form:
            if request.form['password'] == ADMIN_PASSWORD:
                session['pw_verified'] = True
                return render_template('login.html', step='otp')
            return render_template('login.html', step='password', error="Mot de passe incorrect")

        # Étape 2 : OTP
        if 'otp' in request.form:
            if not session.get('pw_verified'):
                return redirect(url_for('login'))
            
            if totp.verify(request.form['otp']):
                session['authenticated'] = True
                session.pop('pw_verified', None)
                return redirect(url_for('index'))
            
            return render_template('login.html', step='otp', error="Code invalide ou expiré")

    # Rendu initial ou étape OTP
    if not session.get('pw_verified'):
        return render_template('login.html', step='password')
    
    # Si on est ici, le mot de passe est bon, on montre le QR Code + champ OTP
    provisioning_uri = totp.provisioning_uri(name="Analyste", issuer_name="SalamaIQ")
    img = qrcode.make(provisioning_uri)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    
    return render_template('login.html', step='setup', qr_code=qr_b64)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

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
    """Enregistre un DataFrame dans la base SQLite (table transaction)."""
    if df.empty:
        return

    # On s'assure d'avoir uniquement les colonnes du modèle
    cols_db = [
        'datetransaction', 'client', 'statut', 
        'volume_gasoil', 'volume_super', 
        'marge_ht', 'ca_total', 'ca', 'achat_ht',
        'prix_achat_gasoil_ht', 'prix_achat_super_ht',
        'prix_vente_gasoil_ttc', 'prix_vente_super_ttc',
        'prix_vente_gasoil_ht', 'prix_vente_super_ht', 'marge_unitaire'
    ]
    
    # Remplir les colonnes manquantes avec NaN si nécessaire
    for c in cols_db:
        if c not in df.columns:
            df[c] = np.nan

    df_db = df[cols_db].copy()

    # Dédoublonnage sur la BDD existante (très basique : date + client + volumes + CA)
    merge_keys = ['datetransaction', 'client', 'volume_gasoil', 'volume_super', 'ca_total']
    try:
        existing_df = load_all_transactions()
        if not existing_df.empty:
            # Ne garder que les colonnes de merge de existing_df pour éviter les suffixes _x/_y
            existing_keys = existing_df[merge_keys].drop_duplicates()
            merged = pd.merge(
                df_db, existing_keys,
                on=merge_keys,
                how='left', indicator=True
            )
            df_db = merged[merged['_merge'] == 'left_only'][cols_db].copy()
    except Exception as e:
        print(f"[SalamaIQ] Info: {e}")

    if df_db.empty:
        print("[SalamaIQ] Aucune nouvelle donnée à insérer (doublons détectés).")
        return

    df_db['batch_id'] = str(uuid.uuid4())

    # Enregistrer en base
    df_db.to_sql('transaction', db.engine, if_exists='append', index=False)
    print(f"[SalamaIQ] {len(df_db)} nouvelles transactions insérées.")


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

    if filters.get('statut') and 'statut' in df_filtered.columns:
        statuts = filters['statut'] if isinstance(filters['statut'], list) else [filters['statut']]
        if statuts and statuts != ['']:
            df_filtered = df_filtered[df_filtered['statut'].isin(statuts)]

    if filters.get('client') and 'client' in df_filtered.columns:
        clients = filters['client'] if isinstance(filters['client'], list) else [filters['client']]
        if clients and clients != ['']:
            df_filtered = df_filtered[df_filtered['client'].isin(clients)]

    if filters.get('years') and 'datetransaction' in df_filtered.columns:
        years = filters['years'] if isinstance(filters['years'], list) else [filters['years']]
        if years and years != ['']:
            try:
                # Convertir les années de string en int
                years_int = sorted([int(y) for y in years])
                
                # On inclut toujours l'année précédant la sélection minimale pour permettre la comparaison N-1
                comparison_years = years_int.copy()
                if not filters.get('date_from') and not filters.get('date_to'):
                    prev_year = min(years_int) - 1
                    comparison_years.append(prev_year)
                
                df_filtered = df_filtered[df_filtered['datetransaction'].dt.year.isin(comparison_years)]
            except Exception:
                pass

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
    spread = get_spread_analysis(df)
    profitability = get_client_profitability(df)

    # Listes pour les filtres
    statuts = sorted(df['statut'].dropna().unique().tolist()) if 'statut' in df.columns else []
    clients = sorted(df['client'].dropna().unique().tolist()) if 'client' in df.columns else []
    
    years = []
    if 'datetransaction' in df.columns:
        years = sorted(df['datetransaction'].dt.year.dropna().unique().tolist(), reverse=True)

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


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def index():
    """Page principale unifiée : charge le Dashboard depuis la BDD ou affiche l'état vide."""
    session_id = get_session_id()
    df = get_dataframe(session_id)

    # Si aucune donnée en BDD → état vide (on passe db_empty=True au template)
    if df is None or df.empty:
        empty_kpis = {
            'ca_total': 0, 'ca_total_n1': 0, 'ca_variation': None,
            'volume_total': 0, 'volume_total_n1': 0, 'vol_total_variation': None,
            'volume_gasoil': 0, 'volume_gasoil_n1': 0, 'vol_gasoil_variation': None,
            'volume_super': 0, 'volume_super_n1': 0, 'vol_super_variation': None,
            'marge_ht': 0, 'marge_ht_n1': 0, 'marge_variation': None,
            'taux_marge': 0, 'taux_marge_n1': 0,
            'marge_unitaire': 0, 'marge_unitaire_n1': 0, 'marge_unitaire_variation': None,
            'current_year': 0, 'previous_year': 0,
            'date_debut': '—', 'date_fin': '—',
            'total_transactions': 0, 'nb_clients': 0, 'nb_statuts': 0,
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
            spread=json.dumps({}),
            profitability=json.dumps([]),
            filters_data=json.dumps({'statuts': [], 'clients': [], 'date_min': '', 'date_max': ''}),
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
        spread=json.dumps(dashboard_data['spread'], cls=NumpyEncoder),
        profitability=json.dumps(dashboard_data['profitability'], cls=NumpyEncoder),
        filters_data=json.dumps(dashboard_data['filters_data'], cls=NumpyEncoder),
        diagnostic="",
        nb_rows=len(df),
        columns_found=[],
        red_flags=[],
        db_empty=False,
    )


@app.route('/download-template', methods=['GET'])
def download_template():
    """Génère et télécharge le modèle Excel vierge."""
    import io
    from processing.normalizer import REQUIRED_COLUMNS
    
    df_template = pd.DataFrame(columns=REQUIRED_COLUMNS)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_template.to_excel(writer, index=False, sheet_name='Modele_Import')
        # Ajuster la largeur des colonnes
        worksheet = writer.sheets['Modele_Import']
        for i, col in enumerate(REQUIRED_COLUMNS):
            worksheet.set_column(i, i, max(len(col) + 5, 15))
            
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name='Modele_SalamaIQ.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@app.route('/upload', methods=['POST'])
@login_required
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
            return jsonify({'status': 'error', 'message': "Aucun fichier sélectionné."}), 400
    else:
        files = request.files.getlist('files')

    if not files or all(f.filename == '' for f in files):
        return jsonify({'status': 'error', 'message': "Fichiers invalides."}), 400

    dfs_to_concat = []
    final_mapping = {}
    filenames = []
    mapping_source = "Normalisation Standard"

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

            # ── Étape 3 : Normalisation (Pandas) ─────────────────────────────────
            df_norm, mapping = normalize_dataframe(df_raw, {})
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
        return jsonify({'status': 'error', 'message': "Aucune donnée valide n'a pu être extraite des fichiers fournis."}), 400

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
        spread=json.dumps(dashboard_data['spread'], cls=NumpyEncoder),
        profitability=json.dumps(dashboard_data['profitability'], cls=NumpyEncoder),
        filters_data=json.dumps(dashboard_data['filters_data'], cls=NumpyEncoder),
        nb_rows=len(df_history),
        columns_found=list(final_mapping.values()),
        red_flags=red_flags,
    )





@app.route('/api/filtered-data', methods=['GET'])
@login_required
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
            'statut': request.args.getlist('statut'),
            'client': request.args.getlist('client'),
            'years': request.args.getlist('years'),
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
            'product_mix': dashboard_data['product_mix'],
            'cumulative': dashboard_data['cumulative'],
            'client_bubble': dashboard_data['client_bubble'],
            'heatmap': dashboard_data['heatmap'],
            'spread': dashboard_data['spread'],
            'profitability': dashboard_data['profitability'],
            'nb_rows': len(df_filtered),
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate-client-pdf', methods=['GET'])
@login_required
def export_client_pdf():
    """Génère un rapport PDF professionnel côté backend"""
    try:
        session_id = request.args.get('session_id', get_session_id())
        df = get_dataframe(session_id)
        if df is None or df.empty:
            return "Aucune donnée disponible", 404

        # Appliquer les mêmes filtres que le dashboard
        filters = {
            'date_from': request.args.get('date_from'),
            'date_to': request.args.get('date_to'),
            'statut': request.args.getlist('statut'),
            'client': request.args.getlist('client'),
            'years': request.args.getlist('years'),
        }
        df_filtered = apply_filters(df, filters)
        
        if df_filtered.empty:
            return "Aucune donnée pour ces filtres", 404

        # Préparer les KPIs pour le PDF
        dashboard_data = prepare_dashboard_data(df_filtered)
        kpis = dashboard_data['kpis']
        
        # Déterminer les labels d'en-tête
        client_label = ", ".join(filters['client']) if filters['client'] else "Tous les clients"
        
        d_min = df_filtered['datetransaction'].min()
        d_max = df_filtered['datetransaction'].max()
        p_start = d_min.strftime('%d/%m/%Y') if pd.notnull(d_min) else 'N/A'
        p_end = d_max.strftime('%d/%m/%Y') if pd.notnull(d_max) else 'N/A'
        period_label = f"{p_start} au {p_end}"
        
        # Générer le PDF (binaire)
        print(f">>> [PDF] Début génération pour {len(df_filtered)} lignes", flush=True)
        pdf_content = generate_client_report(kpis, df_filtered, client_label, period_label)
        print(f">>> [PDF] Binaire généré: {len(pdf_content)} octets", flush=True)
        
        # Préparer le nom du fichier (ASCII uniquement pour éviter les bugs de téléchargement)
        from urllib.parse import quote
        safe_client = client_label.replace(' ', '_').replace(',', '_')
        safe_client = "".join(c for c in safe_client if c.isalnum() or c == '_')
        filename = f"Rapport_SalamaIQ_{safe_client}_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        import io
        return send_file(
            io.BytesIO(pdf_content),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        print(f">>> [PDF] ERREUR: {str(e)}", flush=True)
        import traceback
        traceback.print_exc()
        return f"Erreur lors de la génération du PDF: {str(e)}", 500
        return f"Erreur lors de la génération du PDF: {str(e)}", 500


@app.route('/api/transactions', methods=['GET'])
@login_required
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
    """Retourne les listes de statuts et clients disponibles."""
    try:
        session_id = request.args.get('session_id', get_session_id())
        df = get_dataframe(session_id)

        if df is None:
            return jsonify({'statuts': [], 'clients': []})

        return jsonify({
            'statuts': sorted(df['statut'].dropna().unique().tolist()) if 'statut' in df.columns else [],
            'clients': sorted(df['client'].dropna().unique().tolist()) if 'client' in df.columns else [],
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/purge', methods=['POST'])
@login_required
def api_purge():
    try:
        clear_database()
        return jsonify({'status': 'success', 'message': 'Historique purgé avec succès.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500



# ─── Routes BDD Manager (CRUD) ───────────────────────────────────────────────

@app.route('/api/transactions/add', methods=['POST'])
@login_required
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
            statut=data.get('statut', ''),
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
@login_required
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
        tx.statut = data.get('statut', tx.statut)
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
@login_required
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
    print("  Version 2.0 | Powered by Pandas")
    print("  Dashboard : http://127.0.0.1:5000")
    print("=" * 55)
    app.run(debug=True, port=5000, host='0.0.0.0')
