import os
import sys
import pandas as pd
from dotenv import load_dotenv

# Load environment before anything
load_dotenv()

# Import processing modules
from processing.ingestion import read_file
from processing.ai_mapper import map_columns
from processing.normalizer import normalize_dataframe
from processing.calculator import (
    compute_kpis, get_monthly_series, get_top10_clients, 
    get_margin_bridge, get_product_mix, get_cumulative_series, 
    get_client_bubble, get_monthly_heatmap, get_data_summary_for_chat
)

def run_test(filepath):
    print(f"=== TEST SALAMAIQ PIPELINE START ===")
    print(f"File: {filepath}")
    
    # 1. Ingestion
    print("\n--- 1. Ingestion ---")
    df_raw, raw_headers = read_file(filepath)
    if df_raw.empty:
        print("ERROR: File is empty or could not be read.")
        return
    print(f"Loaded {len(df_raw)} rows, {len(df_raw.columns)} columns.")
    print(f"Raw headers: {df_raw.columns.tolist()}")
    
    # 2. AI Mapping
    print("\n--- 2. AI Mapping ---")
    mapping = map_columns(df_raw.columns.tolist())
    print(f"AI Mapping Result: {mapping}")
    
    # 3. Normalization
    print("\n--- 3. Normalization ---")
    df_clean, final_map = normalize_dataframe(df_raw, mapping)
    print(f"Final mapping used: {final_map}")
    print(f"Columns after normalization: {df_clean.columns.tolist()}")
    print("\nData sample (first 3 rows):")
    print(df_clean.head(3).to_string())
    print("\nData summary:")
    print(df_clean.info())
    print("\nNull values:")
    print(df_clean.isnull().sum())
    
    # 4. Calculation (KPIs)
    print("\n--- 4. Calculation ---")
    kpis = compute_kpis(df_clean)
    print("\n--- KPIs ---")
    for k, v in kpis.items():
        print(f"  {k}: {v}")
        
    monthly = get_monthly_series(df_clean)
    print("\n--- Monthly Series lengths ---")
    for k, v in monthly.items():
        print(f"  {k}: {len(v) if isinstance(v, list) else v}")
        
    top10 = get_top10_clients(df_clean)
    print("\n--- Top 10 Clients ---")
    for i, c in enumerate(top10):
        print(f"  {i+1}. {c['client']} | CA: {c['ca']} | GO: {c['volume_gasoil']} | SP: {c['volume_super']} | Marge: {c['marge']}")
        
    bridge = get_margin_bridge(df_clean)
    print("\n--- Margin Bridge ---")
    print(f"  Categories: {bridge['categories']}")
    print(f"  Values: {bridge['values']}")
    print(f"  Total: {bridge['total']}")
    
    product_mix = get_product_mix(df_clean)
    print("\n--- Product Mix ---")
    print(f"  {product_mix}")
    
    chat_summary = get_data_summary_for_chat(df_clean, kpis)
    print("\n--- Chat Summary ---")
    print(chat_summary)
    
    print("\n=== TEST FINISHED ===")

if __name__ == "__main__":
    filepath = "C:/Users/Yassine/Documents/smcanalyst/Book1test.xlsx"
    run_test(filepath)
