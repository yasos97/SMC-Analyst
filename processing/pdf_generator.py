import os
import io
import tempfile
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from fpdf import FPDF
from datetime import datetime

def clean_text(text):
    """Sanitize text for Helvetica font (replaces non-latin1 characters)"""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    # Remplacements courants
    text = text.replace('—', '-').replace('–', '-').replace('\u2019', "'").replace('\u201c', '"').replace('\u201d', '"')
    # Garder uniquement ce qui est compatible Latin-1 (Helvetica standard)
    return text.encode('latin-1', 'replace').decode('latin-1').replace('?', '')

class SalamaPDF(FPDF):
    def header(self):
        # Logo placeholder (Text based for now as no image available)
        self.set_font('helvetica', 'B', 20)
        self.set_text_color(232, 50, 26)  # Salama Red
        self.cell(40, 10, 'Salama', ln=0)
        self.set_text_color(15, 23, 42)  # Dark Blue
        self.cell(20, 10, 'IQ', ln=1)
        
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(100, 116, 139)
        self.cell(0, 5, "Plateforme d'Analyse Analytique", ln=1)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 10, f'Page {self.page_no()} | Généré le {datetime.now().strftime("%d/%m/%Y %H:%M")}', align='C')

def generate_client_report(data_kpis, df_transactions, client_name="Tous les clients", period="N/A", compare=True):
    pdf = SalamaPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Liste des fichiers temporaires à nettoyer à la fin
    temp_files = []
    
    # ── Header Infos ─────────────────────────────────────────────────────────
    pdf.set_font('helvetica', 'B', 16)
    pdf.set_text_color(15, 23, 42)
    titre = 'RELEVE DE CONSOMMATION CLIENT' if compare else "ANALYSE D'ACTIVITE"
    pdf.cell(0, 10, clean_text(titre), ln=1, align='C')
    pdf.ln(5)
    
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(30, 7, clean_text('Client :'), border=0)
    pdf.set_font('helvetica', '', 10)
    pdf.cell(0, 7, clean_text(client_name), ln=1)
    
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(30, 7, clean_text('Periode :'), border=0)
    pdf.set_font('helvetica', '', 10)
    pdf.cell(0, 7, clean_text(period), ln=1)
    pdf.ln(6)
    
    # ── Texte de synthese dynamique ──────────────────────────────────────────
    ca_val = data_kpis.get('ca_total', 0)
    vol_val = data_kpis.get('volume_total', 0)
    ca_var = data_kpis.get('ca_variation', 0)
    
    pdf.set_font('helvetica', '', 10)
    pdf.set_text_color(71, 85, 105)
    
    intro_text = f"Ce rapport presente une synthese detaillee de l'activite de {client_name} sur la periode du {period}. "
    intro_text += f"Au cours de cette periode, le chiffre d'affaires s'etablit a {ca_val:,.2f} MAD pour un volume total ecoule de {vol_val:,.0f} Litres. ".replace(',', ' ')
    
    if compare and ca_var is not None and ca_var != 0:
        if ca_var > 5:
            intro_text += f"L'activite enregistre une excellente performance avec une croissance de +{ca_var:.1f}% par rapport a l'annee precedente."
        elif ca_var > 0:
            intro_text += f"L'activite est en legere hausse de +{ca_var:.1f}% par rapport a l'annee precedente."
        elif ca_var < -5:
            intro_text += f"On constate malheureusement un recul significatif de l'activite de {ca_var:.1f}% par rapport a l'annee precedente."
        else:
            intro_text += f"L'activite est en legere baisse de {ca_var:.1f}% par rapport a l'annee precedente."
            
    pdf.multi_cell(0, 5.5, clean_text(intro_text))
    pdf.ln(8)
    
    # ── KPI Summary Grid ─────────────────────────────────────────────────────
    pdf.set_fill_color(248, 250, 252)
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(0, 10, clean_text(" RESUME DE L'ACTIVITE"), ln=1, fill=True)
    pdf.ln(5)
    
    # Grid Layout
    col_w = 45
    h = 20
    
    def draw_kpi_box(x, y, label, value, unit):
        pdf.set_xy(x, y)
        pdf.set_draw_color(226, 232, 240)
        pdf.rect(x, y, col_w, h)
        pdf.set_xy(x + 2, y + 4)
        pdf.set_font('helvetica', '', 8)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(col_w-4, 4, clean_text(label), align='C', ln=1)
        pdf.set_xy(x + 2, y + 10)
        pdf.set_font('helvetica', 'B', 10)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(col_w-4, 5, clean_text(f"{value} {unit}"), align='C')

    start_y = pdf.get_y()
    draw_kpi_box(10, start_y, "Chiffre d'Affaires", f"{data_kpis.get('ca_total', 0):,.2f}".replace(',', ' '), "MAD")
    draw_kpi_box(10 + col_w + 5, start_y, "Volume Total", f"{data_kpis.get('volume_total', 0):,.0f}".replace(',', ' '), "L")
    draw_kpi_box(10 + (col_w + 5)*2, start_y, "Volume Gasoil", f"{data_kpis.get('volume_gasoil', 0):,.0f}".replace(',', ' '), "L")
    draw_kpi_box(10 + (col_w + 5)*3, start_y, "Volume Super", f"{data_kpis.get('volume_super', 0):,.0f}".replace(',', ' '), "L")
    
    pdf.set_xy(10, start_y + h + 10)
    
    # ── Chart ────────────────────────────────────────────────────────────────
    if not df_transactions.empty:
        # Prepare chart
        df_plot = df_transactions.copy()
        df_plot['year'] = df_plot['datetransaction'].dt.year
        df_plot['month_num'] = df_plot['datetransaction'].dt.month
        
        years = sorted(df_plot['year'].unique(), reverse=True)
        current_year = years[0] if len(years) > 0 else 2025
        previous_year = years[1] if len(years) > 1 else current_year - 1

        df_n = df_plot[df_plot['year'] == current_year]
        df_n1 = df_plot[df_plot['year'] == previous_year]

        vol_n = df_n.groupby('month_num')[['volume_gasoil', 'volume_super']].sum().reindex(range(1, 13), fill_value=0)
        vol_n1 = df_n1.groupby('month_num')[['volume_gasoil', 'volume_super']].sum().reindex(range(1, 13), fill_value=0)

        labels = ['Jan', 'Fev', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Aout', 'Sep', 'Oct', 'Nov', 'Dec']
        import numpy as np
        x = np.arange(12)
        width = 0.35

        fig, ax = plt.subplots(figsize=(9, 4.0))
        plt.style.use('bmh')
        
        if compare:
            # N-1 Bars (Couleurs plus claires)
            ax.bar(x - width/2, vol_n1['volume_gasoil'], width, label=f'Gasoil ({previous_year})', color='#fef08a')
            ax.bar(x - width/2, vol_n1['volume_super'], width, bottom=vol_n1['volume_gasoil'], label=f'Super ({previous_year})', color='#fdba74')
    
            # N Bars (Couleurs foncées)
            ax.bar(x + width/2, vol_n['volume_gasoil'], width, label=f'Gasoil ({current_year})', color='#eab308')
            ax.bar(x + width/2, vol_n['volume_super'], width, bottom=vol_n['volume_gasoil'], label=f'Super ({current_year})', color='#f97316')
            ax.set_title(f'Consommation Mensuelle (N vs N-1) - {client_name}', fontsize=12, fontweight='bold', pad=15)
        else:
            # N Bars Only
            ax.bar(x, vol_n['volume_gasoil'], width, label=f'Gasoil ({current_year})', color='#eab308')
            ax.bar(x, vol_n['volume_super'], width, bottom=vol_n['volume_gasoil'], label=f'Super ({current_year})', color='#f97316')
            ax.set_title(f'Consommation Mensuelle - {client_name}', fontsize=12, fontweight='bold', pad=15)

        ax.set_ylabel('Volume (L)')
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=0, fontsize=9)
        ax.legend(loc='upper right', fontsize=8, ncol=2)
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        plt.tight_layout()
        
        # Sauvegarder dans un fichier temporaire (fpdf ne supporte pas BytesIO)
        tmp_bar = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        plt.savefig(tmp_bar.name, format='png', dpi=150)
        plt.close()
        temp_files.append(tmp_bar.name)
        
        pdf.image(tmp_bar.name, x=15, y=pdf.get_y(), w=180)
        
        # Saut de page pour éviter les chevauchements
        pdf.add_page()

    # ── Donut Chart (Répartition) ────────────────────────────────────────────
    vol_go = data_kpis.get('volume_gasoil', 0)
    vol_sp = data_kpis.get('volume_super', 0)
    vol_go_n1 = data_kpis.get('volume_gasoil_n1', 0)
    vol_sp_n1 = data_kpis.get('volume_super_n1', 0)
    curr_yr = data_kpis.get('current_year', 'N')
    prev_yr = data_kpis.get('previous_year', 'N-1')
    
    if vol_go + vol_sp > 0:
        has_n1 = (vol_go_n1 + vol_sp_n1) > 0
        
        if compare and has_n1:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5))
            
            # Donut N-1
            labels_n1 = [f'Gasoil ({vol_go_n1:,.0f} L)'.replace(',', ' '), f'Super ({vol_sp_n1:,.0f} L)'.replace(',', ' ')]
            ax1.pie([vol_go_n1, vol_sp_n1], labels=labels_n1, colors=['#fef08a', '#fdba74'], autopct='%1.1f%%', 
                    startangle=140, wedgeprops={'width': 0.5}, pctdistance=0.75, textprops={'fontsize': 9})
            ax1.set_title(f'Mix Produit - {prev_yr}', fontsize=12, fontweight='bold', pad=10)
            
            # Donut N
            labels_n = [f'Gasoil ({vol_go:,.0f} L)'.replace(',', ' '), f'Super ({vol_sp:,.0f} L)'.replace(',', ' ')]
            ax2.pie([vol_go, vol_sp], labels=labels_n, colors=['#eab308', '#f97316'], autopct='%1.1f%%', 
                    startangle=140, wedgeprops={'width': 0.5}, pctdistance=0.75, textprops={'fontsize': 9})
            ax2.set_title(f'Mix Produit - {curr_yr}', fontsize=12, fontweight='bold', pad=10)
            
            plt.suptitle('Repartition du Mix Produit (N vs N-1)', fontsize=14, fontweight='bold')
            plt.tight_layout()
            
            tmp_donut = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            plt.savefig(tmp_donut.name, format='png', dpi=150)
            plt.close()
            temp_files.append(tmp_donut.name)
            
            pdf.image(tmp_donut.name, x=15, y=pdf.get_y(), w=180)
            
        else:
            plt.figure(figsize=(6, 4.5))
            labels_donut = [f'Gasoil ({vol_go:,.0f} L)'.replace(',', ' '), f'Super ({vol_sp:,.0f} L)'.replace(',', ' ')]
            plt.pie([vol_go, vol_sp], labels=labels_donut, colors=['#eab308', '#f97316'], autopct='%1.1f%%', 
                    startangle=140, wedgeprops={'width': 0.5}, pctdistance=0.75, textprops={'fontsize': 10})
            plt.title(f'Repartition du Mix Produit - {curr_yr}', fontsize=14, fontweight='bold', pad=20)
            plt.axis('equal')
            plt.tight_layout()

            tmp_donut = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            plt.savefig(tmp_donut.name, format='png', dpi=150)
            plt.close()
            temp_files.append(tmp_donut.name)

            pdf.image(tmp_donut.name, x=55, y=pdf.get_y(), w=100)

    # Générer le PDF via un fichier temporaire (fpdf ancien ne gère pas bien les bytes en mémoire)
    tmp_pdf = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    tmp_pdf.close()
    pdf.output(tmp_pdf.name)
    
    with open(tmp_pdf.name, 'rb') as f:
        pdf_bytes = f.read()
    
    # Nettoyer tous les fichiers temporaires (images + PDF)
    temp_files.append(tmp_pdf.name)
    for f in temp_files:
        try:
            os.unlink(f)
        except OSError:
            pass
    
    return pdf_bytes
