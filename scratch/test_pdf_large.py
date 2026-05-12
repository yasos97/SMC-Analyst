import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from processing.pdf_generator import generate_client_report

# Mock data (2000 rows)
kpis = {
    'ca_total': 1250000.50,
    'volume_total': 150000,
    'volume_gasoil': 100000,
    'volume_super': 50000,
    'date_debut': '01/01/2024',
    'date_fin': '31/03/2024'
}

dates = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(2000)]
df = pd.DataFrame({
    'datetransaction': dates,
    'client': ['Client ' + str(i % 100) for i in range(2000)],
    'produit': ['Gasoil' if i % 2 == 0 else 'Super SP' for i in range(2000)],
    'volume_gasoil': [100 if i % 2 == 0 else 0 for i in range(2000)],
    'volume_super': [0 if i % 2 == 0 else 100 for i in range(2000)],
    'ca_total': [1200 if i % 2 == 0 else 1500 for i in range(2000)]
})

try:
    print("Starting PDF generation for 2000 rows...")
    pdf_bytes = generate_client_report(kpis, df, "Test Client", "01/2024 - 03/2024")
    with open("test_report_large.pdf", "wb") as f:
        f.write(pdf_bytes)
    print(f"PDF generated successfully: test_report_large.pdf ({len(pdf_bytes)} bytes)")
except Exception as e:
    print(f"Error generating PDF: {str(e)}")
    import traceback
    traceback.print_exc()
