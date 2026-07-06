"""
SalamaIQ - Generateur de Rapports Excel
=========================================
Genere un classeur Excel professionnel avec :
  - Feuille Resume (KPIs + graphiques)
  - Feuille Evolution Mensuelle (tableau + graphique)
  - Feuille Top 10 Clients
  - Feuille Detail Transactions
"""

import io
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.chart.series import DataPoint, SeriesLabel
from openpyxl.chart.label import DataLabelList
from openpyxl.utils import get_column_letter
from datetime import datetime


# ── Couleurs SalamaIQ ──────────────────────────────────────────────────────────
SALAMA_RED = 'E8321A'
DARK_BLUE = '0F172A'
SLATE_600 = '475569'
LIGHT_BG = 'F8FAFC'
WHITE = 'FFFFFF'
BORDER_COLOR = 'E2E8F0'

# Styles reusables
HEADER_FONT = Font(name='Calibri', bold=True, size=11, color=WHITE)
HEADER_FILL = PatternFill(start_color=DARK_BLUE, end_color=DARK_BLUE, fill_type='solid')
TITLE_FONT = Font(name='Calibri', bold=True, size=16, color=DARK_BLUE)
SUBTITLE_FONT = Font(name='Calibri', bold=True, size=12, color=SALAMA_RED)
KPI_VALUE_FONT = Font(name='Calibri', bold=True, size=14, color=DARK_BLUE)
KPI_LABEL_FONT = Font(name='Calibri', size=10, color=SLATE_600)
NORMAL_FONT = Font(name='Calibri', size=10)
THIN_BORDER = Border(
    left=Side(style='thin', color=BORDER_COLOR),
    right=Side(style='thin', color=BORDER_COLOR),
    top=Side(style='thin', color=BORDER_COLOR),
    bottom=Side(style='thin', color=BORDER_COLOR)
)


def _format_number(val, decimals=2):
    """Formate un nombre pour l'affichage."""
    if val is None:
        return 0
    return round(float(val), decimals)


def _apply_table_style(ws, start_row, end_row, start_col, end_col):
    """Applique un style tableau propre a une plage."""
    for row in range(start_row, end_row + 1):
        for col in range(start_col, end_col + 1):
            cell = ws.cell(row=row, column=col)
            cell.border = THIN_BORDER
            cell.alignment = Alignment(horizontal='center', vertical='center')
            if row == start_row:
                cell.font = HEADER_FONT
                cell.fill = HEADER_FILL
            else:
                cell.font = NORMAL_FONT
                if row % 2 == 0:
                    cell.fill = PatternFill(start_color=LIGHT_BG, end_color=LIGHT_BG, fill_type='solid')


def generate_excel_report(data_kpis, df_transactions, client_name="Tous les clients", period="N/A", compare=True):
    """
    Genere un rapport Excel complet avec graphiques.
    
    Args:
        data_kpis: dict des KPIs (depuis compute_kpis)
        df_transactions: DataFrame filtre
        client_name: Nom du client
        period: Periode d'analyse
        compare: Si True, inclut les donnees N-1
    
    Returns:
        bytes du fichier Excel
    """
    wb = Workbook()
    
    # ─────────────────────────────────────────────────────────────────────────
    # FEUILLE 1 : RESUME
    # ─────────────────────────────────────────────────────────────────────────
    ws_resume = wb.active
    ws_resume.title = "Resume"
    ws_resume.sheet_properties.tabColor = SALAMA_RED
    
    # Titre
    ws_resume.merge_cells('A1:H1')
    cell_title = ws_resume['A1']
    titre = "RELEVE DE CONSOMMATION CLIENT" if compare else "ANALYSE D'ACTIVITE"
    cell_title.value = f"SalamaIQ - {titre}"
    cell_title.font = TITLE_FONT
    cell_title.alignment = Alignment(horizontal='center', vertical='center')
    ws_resume.row_dimensions[1].height = 35
    
    # Info client / periode
    ws_resume.merge_cells('A2:H2')
    ws_resume['A2'].value = f"Client : {client_name}  |  Periode : {period}  |  Genere le {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    ws_resume['A2'].font = Font(name='Calibri', size=10, color=SLATE_600)
    ws_resume['A2'].alignment = Alignment(horizontal='center')
    ws_resume.row_dimensions[2].height = 25
    
    # ── KPIs ──
    ws_resume.merge_cells('A4:H4')
    ws_resume['A4'].value = "INDICATEURS CLES"
    ws_resume['A4'].font = SUBTITLE_FONT
    
    current_year = data_kpis.get('current_year', 'N')
    previous_year = data_kpis.get('previous_year', 'N-1')
    
    # En-tetes KPI
    row = 6
    if compare:
        headers = ['Indicateur', f'Valeur {current_year}', f'Valeur {previous_year}', 'Variation (%)', 'Unite']
    else:
        headers = ['Indicateur', f'Valeur {current_year}', 'Unite']
    
    for col_idx, h in enumerate(headers, 1):
        cell = ws_resume.cell(row=row, column=col_idx, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = THIN_BORDER
    
    # Donnees KPI
    kpi_rows = [
        ("Chiffre d'Affaires HT", 'ca_total', 'ca_total_n1', 'ca_variation', 'MAD'),
        ("Volume Total", 'volume_total', 'volume_total_n1', 'vol_total_variation', 'L'),
        ("Volume Gasoil", 'volume_gasoil', 'volume_gasoil_n1', 'vol_gasoil_variation', 'L'),
        ("Volume Super SP", 'volume_super', 'volume_super_n1', 'vol_super_variation', 'L'),
    ]
    
    for i, (label, key_n, key_n1, key_var, unit) in enumerate(kpi_rows):
        r = row + 1 + i
        val_n = _format_number(data_kpis.get(key_n, 0))
        
        if compare:
            val_n1 = _format_number(data_kpis.get(key_n1, 0))
            variation = data_kpis.get(key_var) if key_var else None
            
            ws_resume.cell(row=r, column=1, value=label).font = Font(name='Calibri', bold=True, size=10)
            ws_resume.cell(row=r, column=2, value=val_n).number_format = '#,##0.00'
            ws_resume.cell(row=r, column=3, value=val_n1).number_format = '#,##0.00'
            
            var_cell = ws_resume.cell(row=r, column=4)
            if variation is not None:
                var_cell.value = variation / 100
                var_cell.number_format = '+0.0%;-0.0%'
                var_cell.font = Font(name='Calibri', bold=True, size=10, 
                                     color='16A34A' if variation >= 0 else 'DC2626')
            else:
                var_cell.value = "N/A"
            
            ws_resume.cell(row=r, column=5, value=unit)
        else:
            ws_resume.cell(row=r, column=1, value=label).font = Font(name='Calibri', bold=True, size=10)
            ws_resume.cell(row=r, column=2, value=val_n).number_format = '#,##0.00'
            ws_resume.cell(row=r, column=3, value=unit)
        
        # Bordures
        for c in range(1, len(headers) + 1):
            cell = ws_resume.cell(row=r, column=c)
            cell.border = THIN_BORDER
            cell.alignment = Alignment(horizontal='center', vertical='center')
            if r % 2 == 0:
                cell.fill = PatternFill(start_color=LIGHT_BG, end_color=LIGHT_BG, fill_type='solid')
    
    # Ajuster largeurs colonnes Resume
    ws_resume.column_dimensions['A'].width = 25
    for col_letter in ['B', 'C', 'D', 'E', 'F', 'G', 'H']:
        ws_resume.column_dimensions[col_letter].width = 18
    
    # ─────────────────────────────────────────────────────────────────────────
    # EVOLUTION MENSUELLE ET MIX PRODUIT (FEUILLES 2, 3, 4)
    # ─────────────────────────────────────────────────────────────────────────
    month_labels = ['Jan', 'Fev', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Aout', 'Sep', 'Oct', 'Nov', 'Dec']
    
    if not df_transactions.empty and 'datetransaction' in df_transactions.columns:
        df_plot = df_transactions.copy()
        df_plot['year'] = df_plot['datetransaction'].dt.year
        df_plot['month_num'] = df_plot['datetransaction'].dt.month
        
        years = sorted(df_plot['year'].unique(), reverse=True)
        current_yr = years[0] if len(years) > 0 else 2025
        previous_yr = years[1] if len(years) > 1 else current_yr - 1
        
        df_n = df_plot[df_plot['year'] == current_yr]
        df_n1 = df_plot[df_plot['year'] == previous_yr]
        
        # Aggregations mensuelles
        def monthly_sum(df_yr, col):
            if df_yr.empty or col not in df_yr.columns:
                return [0.0] * 12
            grp = df_yr.groupby('month_num')[col].sum()
            return [round(float(grp.get(m, 0.0)), 2) for m in range(1, 13)]
        
        vol_gasoil_n = monthly_sum(df_n, 'volume_gasoil')
        vol_super_n = monthly_sum(df_n, 'volume_super')
        
        vol_gasoil_n1 = monthly_sum(df_n1, 'volume_gasoil')
        vol_super_n1 = monthly_sum(df_n1, 'volume_super')
        
        def create_evolution_sheet(sheet_name, title, product_name, color_n, color_n1, data_n, data_n1):
            ws = wb.create_sheet(sheet_name)
            ws.sheet_properties.tabColor = color_n
            
            ws['A1'].value = title
            ws['A1'].font = SUBTITLE_FONT
            ws.merge_cells('A1:N1')
            
            # En-tetes
            r = 3
            headers_m = ['Annee'] + month_labels + ['TOTAL']
            for ci, h in enumerate(headers_m, 1):
                cell = ws.cell(row=r, column=ci, value=h)
                cell.font = HEADER_FONT
                cell.fill = HEADER_FILL
                cell.alignment = Alignment(horizontal='center')
                cell.border = THIN_BORDER
            
            # Ligne N
            r = 4
            ws.cell(row=r, column=1, value=str(current_yr)).font = Font(name='Calibri', bold=True, size=10)
            for ci, val in enumerate(data_n, 2):
                ws.cell(row=r, column=ci, value=val).number_format = '#,##0'
            ws.cell(row=r, column=14, value=sum(data_n)).number_format = '#,##0'
            
            if compare:
                # Ligne N-1
                r = 5
                ws.cell(row=r, column=1, value=str(previous_yr)).font = Font(name='Calibri', bold=True, size=10)
                for ci, val in enumerate(data_n1, 2):
                    ws.cell(row=r, column=ci, value=val).number_format = '#,##0'
                ws.cell(row=r, column=14, value=sum(data_n1)).number_format = '#,##0'
                
                # Ligne Variation
                r = 6
                ws.cell(row=r, column=1, value='Variation').font = Font(name='Calibri', bold=True, size=10, color=SALAMA_RED)
                for ci in range(12):
                    if data_n1[ci] > 0:
                        var = (data_n[ci] - data_n1[ci]) / data_n1[ci]
                        var_cell = ws.cell(row=r, column=ci+2, value=var)
                        var_cell.number_format = '+0.0%;-0.0%'
                        var_cell.font = Font(name='Calibri', bold=True, size=10, color='16A34A' if var >= 0 else 'DC2626')
                    else:
                        ws.cell(row=r, column=ci+2, value='N/A')
                last_data_row = 6
            else:
                last_data_row = 4
                
            # Bordures tableau
            for rr in range(3, last_data_row + 1):
                for cc in range(1, 15):
                    cell = ws.cell(row=rr, column=cc)
                    cell.border = THIN_BORDER
                    cell.alignment = Alignment(horizontal='center')
                    if rr > 3 and rr % 2 == 0:
                        cell.fill = PatternFill(start_color=LIGHT_BG, end_color=LIGHT_BG, fill_type='solid')
                        
            # Graphique
            chart = BarChart()
            chart.type = "col"
            chart.title = f"Evolution Volume {product_name} - {client_name}"
            chart.y_axis.title = "Volume (L)"
            chart.style = 10
            chart.width = 30
            chart.height = 15
            
            cats = Reference(ws, min_col=2, max_col=13, min_row=3)
            data_n_ref = Reference(ws, min_col=1, max_col=13, min_row=4)
            chart.add_data(data_n_ref, from_rows=True, titles_from_data=True)
            chart.set_categories(cats)
            
            # The title is now taken from cell A4 (e.g. "2025")
            # But we want it to be "Gasoil 2025" or "Super SP 2025", 
            # so we can explicitly override the title:
            chart.series[0].title = SeriesLabel(v=f"{product_name} {current_yr}")
            chart.series[0].graphicalProperties.solidFill = color_n
            
            if compare:
                data_n1_ref = Reference(ws, min_col=1, max_col=13, min_row=5)
                chart.add_data(data_n1_ref, from_rows=True, titles_from_data=True)
                chart.series[1].title = SeriesLabel(v=f"{product_name} {previous_yr}")
                chart.series[1].graphicalProperties.solidFill = color_n1
                
            ws.add_chart(chart, f"A{last_data_row + 2}")
            
            # Largeurs colonnes
            ws.column_dimensions['A'].width = 20
            for col_letter in ['B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N']:
                ws.column_dimensions[col_letter].width = 12

        # FEUILLE 2 : EVOLUTION GASOIL
        create_evolution_sheet("Evolution Gasoil", "EVOLUTION MENSUELLE DU VOLUME GASOIL", "Gasoil", "EAB308", "FEF08A", vol_gasoil_n, vol_gasoil_n1)
        
        # FEUILLE 3 : EVOLUTION SUPER
        create_evolution_sheet("Evolution Super", "EVOLUTION MENSUELLE DU VOLUME SUPER SP", "Super SP", "F97316", "FDBA74", vol_super_n, vol_super_n1)

        # ─────────────────────────────────────────────────────────────────────────
        # FEUILLE 4 : MIX PRODUIT
        # ─────────────────────────────────────────────────────────────────────────
        ws_mix = wb.create_sheet("Mix Produit")
        ws_mix.sheet_properties.tabColor = '475569'
        
        ws_mix['A1'].value = "REPARTITION MIX PRODUIT"
        ws_mix['A1'].font = SUBTITLE_FONT
        
        ws_mix.cell(row=3, column=1, value='Produit').font = HEADER_FONT
        ws_mix.cell(row=3, column=1).fill = HEADER_FILL
        ws_mix.cell(row=3, column=1).border = THIN_BORDER
        
        ws_mix.cell(row=3, column=2, value=f'Volume {current_yr} (L)').font = HEADER_FONT
        ws_mix.cell(row=3, column=2).fill = HEADER_FILL
        ws_mix.cell(row=3, column=2).border = THIN_BORDER
        
        if compare:
            ws_mix.cell(row=3, column=3, value=f'Volume {previous_yr} (L)').font = HEADER_FONT
            ws_mix.cell(row=3, column=3).fill = HEADER_FILL
            ws_mix.cell(row=3, column=3).border = THIN_BORDER
        
        # Gasoil
        ws_mix.cell(row=4, column=1, value='Gasoil').border = THIN_BORDER
        ws_mix.cell(row=4, column=2, value=sum(vol_gasoil_n)).number_format = '#,##0'
        ws_mix.cell(row=4, column=2).border = THIN_BORDER
        if compare:
            ws_mix.cell(row=4, column=3, value=sum(vol_gasoil_n1)).number_format = '#,##0'
            ws_mix.cell(row=4, column=3).border = THIN_BORDER
            
        # Super
        ws_mix.cell(row=5, column=1, value='Super SP').border = THIN_BORDER
        ws_mix.cell(row=5, column=2, value=sum(vol_super_n)).number_format = '#,##0'
        ws_mix.cell(row=5, column=2).border = THIN_BORDER
        if compare:
            ws_mix.cell(row=5, column=3, value=sum(vol_super_n1)).number_format = '#,##0'
            ws_mix.cell(row=5, column=3).border = THIN_BORDER
            
        # Total
        ws_mix.cell(row=6, column=1, value='TOTAL').font = Font(name='Calibri', bold=True)
        ws_mix.cell(row=6, column=1).border = THIN_BORDER
        ws_mix.cell(row=6, column=2, value=sum(vol_gasoil_n) + sum(vol_super_n)).font = Font(name='Calibri', bold=True)
        ws_mix.cell(row=6, column=2).number_format = '#,##0'
        ws_mix.cell(row=6, column=2).border = THIN_BORDER
        if compare:
            ws_mix.cell(row=6, column=3, value=sum(vol_gasoil_n1) + sum(vol_super_n1)).font = Font(name='Calibri', bold=True)
            ws_mix.cell(row=6, column=3).number_format = '#,##0'
            ws_mix.cell(row=6, column=3).border = THIN_BORDER
            
        # Largeurs colonnes
        ws_mix.column_dimensions['A'].width = 25
        ws_mix.column_dimensions['B'].width = 20
        ws_mix.column_dimensions['C'].width = 20
            
        # Graphique Mix N
        chart_pie_n = PieChart()
        chart_pie_n.title = f"Mix Produit {current_yr}"
        chart_pie_n.style = 10
        chart_pie_n.width = 14
        chart_pie_n.height = 12
        
        labels_pie = Reference(ws_mix, min_col=1, min_row=4, max_row=5)
        data_pie_n = Reference(ws_mix, min_col=2, min_row=3, max_row=5)
        chart_pie_n.add_data(data_pie_n, titles_from_data=True)
        chart_pie_n.set_categories(labels_pie)
        
        # Couleurs personnalisees
        s = chart_pie_n.series[0]
        pt_gasoil = DataPoint(idx=0)
        pt_gasoil.graphicalProperties.solidFill = "EAB308"
        s.data_points.append(pt_gasoil)
        pt_super = DataPoint(idx=1)
        pt_super.graphicalProperties.solidFill = "F97316"
        s.data_points.append(pt_super)
        
        chart_pie_n.dataLabels = DataLabelList()
        chart_pie_n.dataLabels.showPercent = True
        chart_pie_n.dataLabels.showVal = True
        
        ws_mix.add_chart(chart_pie_n, "A9")
        
        # Graphique Mix N-1
        if compare:
            chart_pie_n1 = PieChart()
            chart_pie_n1.title = f"Mix Produit {previous_yr}"
            chart_pie_n1.style = 10
            chart_pie_n1.width = 14
            chart_pie_n1.height = 12
            
            data_pie_n1 = Reference(ws_mix, min_col=3, min_row=3, max_row=5)
            chart_pie_n1.add_data(data_pie_n1, titles_from_data=True)
            chart_pie_n1.set_categories(labels_pie)
            
            s1 = chart_pie_n1.series[0]
            pt_gasoil1 = DataPoint(idx=0)
            pt_gasoil1.graphicalProperties.solidFill = "EAB308"
            s1.data_points.append(pt_gasoil1)
            pt_super1 = DataPoint(idx=1)
            pt_super1.graphicalProperties.solidFill = "F97316"
            s1.data_points.append(pt_super1)
            
            chart_pie_n1.dataLabels = DataLabelList()
            chart_pie_n1.dataLabels.showPercent = True
            chart_pie_n1.dataLabels.showVal = True
            
            ws_mix.add_chart(chart_pie_n1, "I9")
    
    # ── Sauvegarder en bytes ──────────────────────────────────────────────────
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()
