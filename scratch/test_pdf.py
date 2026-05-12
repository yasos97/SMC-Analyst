import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from processing.pdf_generator import generate_client_report

# Mock data
kpis = {
    'ca_total': 1250000.50,
    'volume_total': 150000,
    'volume_gasoil': 100000,
    'volume_super': 50000,
    'date_debut': '01/01/2024',
    'date_fin': '31/03/2024'
}

df = pd.DataFrame({
    'datetransaction': pd.to_datetime(['2024-01-15', '2024-02-15', '2024-03-15']),
    'client': ['Client A', 'Client B', 'Client C'],
    'produit': ['Gasoil', 'Super SP', 'Gasoil'],
    'volume_gasoil': [50000, 0, 50000],
    'volume_super': [0, 50000, 0],
    'ca_total': [400000, 450000, 400000]
})

try:
    pdf_bytes = generate_client_report(kpis, df, "Test Client", "01/2024 - 03/2024")
    with open("test_report.pdf", "wb") as f:
        f.write(pdf_bytes)
    print("PDF generated successfully: test_report.pdf")
except Exception as e:
    print(f"Error generating PDF: {str(e)}")
    import traceback
    traceback.print_exc()
