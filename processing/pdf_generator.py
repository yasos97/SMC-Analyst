import os
import io
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
    text = text.replace('—', '-').replace('–', '-').replace('’', "'").replace('“', '"').replace('”', '"')
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
        self.cell(0, 5, 'Plateforme d\'Analyse Analytique', ln=1)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 10, f'Page {self.page_no()} | Généré le {datetime.now().strftime("%d/%m/%Y %H:%M")}', align='C')

def generate_client_report(data_kpis, df_transactions, client_name="Tous les clients", period="N/A"):
    pdf = SalamaPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # ── Header Infos ─────────────────────────────────────────────────────────
    pdf.set_font('helvetica', 'B', 16)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 10, clean_text('RELEVÉ DE CONSOMMATION CLIENT'), ln=1, align='C')
    pdf.ln(5)
    
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(30, 7, clean_text('Client :'), border=0)
    pdf.set_font('helvetica', '', 10)
    pdf.cell(0, 7, clean_text(client_name), ln=1)
    
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(30, 7, clean_text('Période :'), border=0)
    pdf.set_font('helvetica', '', 10)
    pdf.cell(0, 7, clean_text(period), ln=1)
    pdf.ln(10)
    
    # ── KPI Summary Grid ─────────────────────────────────────────────────────
    pdf.set_fill_color(248, 250, 252)
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(0, 10, clean_text(' RÉSUMÉ DE L\'ACTIVITÉ'), ln=1, fill=True)
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

        labels = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc']
        import numpy as np
        x = np.arange(12)
        width = 0.35

        fig, ax = plt.subplots(figsize=(9, 4.0))
        plt.style.use('bmh')
        
        # N-1 Bars (Couleurs plus claires)
        ax.bar(x - width/2, vol_n1['volume_gasoil'], width, label=f'Gasoil ({previous_year})', color='#93c5fd')
        ax.bar(x - width/2, vol_n1['volume_super'], width, bottom=vol_n1['volume_gasoil'], label=f'Super ({previous_year})', color='#fca5a5')

        # N Bars (Couleurs foncées)
        ax.bar(x + width/2, vol_n['volume_gasoil'], width, label=f'Gasoil ({current_year})', color='#2563eb')
        ax.bar(x + width/2, vol_n['volume_super'], width, bottom=vol_n['volume_gasoil'], label=f'Super ({current_year})', color='#dc2626')

        ax.set_ylabel('Volume (L)')
        ax.set_title(f'Consommation Mensuelle (N vs N-1) - {client_name}', fontsize=12, fontweight='bold', pad=15)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=0, fontsize=9)
        ax.legend(loc='upper right', fontsize=8, ncol=2)
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        plt.tight_layout()
        
        img_buf = io.BytesIO()
        plt.savefig(img_buf, format='png', dpi=150)
        img_buf.seek(0)
        plt.close()
        # Draw bar chart
        pdf.image(img_buf, x=15, y=pdf.get_y(), w=180)
        
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
        
        if has_n1:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5))
            
            # Donut N-1
            labels_n1 = [f'Gasoil ({vol_go_n1:,.0f} L)'.replace(',', ' '), f'Super ({vol_sp_n1:,.0f} L)'.replace(',', ' ')]
            ax1.pie([vol_go_n1, vol_sp_n1], labels=labels_n1, colors=['#93c5fd', '#fca5a5'], autopct='%1.1f%%', 
                    startangle=140, wedgeprops={'width': 0.5}, pctdistance=0.75, textprops={'fontsize': 9})
            ax1.set_title(f'Mix Produit - {prev_yr}', fontsize=12, fontweight='bold', pad=10)
            
            # Donut N
            labels_n = [f'Gasoil ({vol_go:,.0f} L)'.replace(',', ' '), f'Super ({vol_sp:,.0f} L)'.replace(',', ' ')]
            ax2.pie([vol_go, vol_sp], labels=labels_n, colors=['#2563eb', '#dc2626'], autopct='%1.1f%%', 
                    startangle=140, wedgeprops={'width': 0.5}, pctdistance=0.75, textprops={'fontsize': 9})
            ax2.set_title(f'Mix Produit - {curr_yr}', fontsize=12, fontweight='bold', pad=10)
            
            plt.suptitle('Répartition du Mix Produit (N vs N-1)', fontsize=14, fontweight='bold')
            plt.tight_layout()
            
            img_buf_donut = io.BytesIO()
            plt.savefig(img_buf_donut, format='png', dpi=150)
            img_buf_donut.seek(0)
            plt.close()
            
            pdf.image(img_buf_donut, x=15, y=pdf.get_y(), w=180)
            
        else:
            plt.figure(figsize=(6, 4.5))
            labels_donut = [f'Gasoil ({vol_go:,.0f} L)'.replace(',', ' '), f'Super ({vol_sp:,.0f} L)'.replace(',', ' ')]
            plt.pie([vol_go, vol_sp], labels=labels_donut, colors=['#2563eb', '#dc2626'], autopct='%1.1f%%', 
                    startangle=140, wedgeprops={'width': 0.5}, pctdistance=0.75, textprops={'fontsize': 10})
            plt.title(f'Répartition du Mix Produit - {curr_yr}', fontsize=14, fontweight='bold', pad=20)
            plt.axis('equal')
            plt.tight_layout()

            img_buf_donut = io.BytesIO()
            plt.savefig(img_buf_donut, format='png', dpi=150)
            img_buf_donut.seek(0)
            plt.close()

            pdf.image(img_buf_donut, x=55, y=pdf.get_y(), w=100)

    return pdf.output()
