import os
import sys
import pandas as pd
from datetime import datetime

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app import app, get_dataframe, apply_filters, prepare_dashboard_data
from processing.pdf_generator import generate_client_report

session_id = "aafa415d-7a0b-4f8e-ac05-7e223e000ecc"

with app.app_context():
    try:
        df = get_dataframe(session_id)
        if df is None or df.empty:
            print("No data in DB for this session.")
            sys.exit(1)
            
        filters = {
            'date_from': '2024-01-03',
            'date_to': '2025-10-31',
            'statut': [],
            'client': [],
            'years': []
        }
        
        print(f"Applying filters... DF size: {len(df)}")
        df_filtered = apply_filters(df, filters)
        print(f"Filtered size: {len(df_filtered)}")
        
        if df_filtered.empty:
            print("Filtered data is empty.")
            sys.exit(1)
            
        print("Preparing KPIs...")
        dashboard_data = prepare_dashboard_data(df_filtered)
        kpis = dashboard_data['kpis']
        
        client_label = "Tous les clients"
        period_label = f"{kpis['date_debut']} au {kpis['date_fin']}"
        
        print("Generating PDF...")
        pdf_content = generate_client_report(kpis, df_filtered, client_label, period_label)
        print(f"PDF generated: {len(pdf_content)} bytes")
        
    except Exception as e:
        print(f"CAUGHT ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
