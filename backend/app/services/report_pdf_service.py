"""
PDF reports for schedule and swaps.

1. generate_swaps_report_pdf — weekly/date-range summary of approved swaps
2. generate_schedule_pdf    — monthly station schedule grid
"""

from __future__ import annotations

import calendar
import io
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_MESES = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

_DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def _is_dark(hex_color: str) -> bool:
    """Return True if the hex color is dark (needs white text)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    # Relative luminance (sRGB)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return luminance < 160


# ═════════════════════════════════════════════════════════
#  1. RELATÓRIO SEMANAL DE TROCAS
# ═════════════════════════════════════════════════════════

def generate_swaps_report_pdf(
    *,
    station_name: str,
    date_from: date,
    date_to: date,
    swaps: List[Dict[str, Any]],
) -> bytes:
    """
    Generate a PDF report listing approved swaps in a date range.

    Each swap dict must contain:
      - requester_name, requester_shift_type, requester_date, requester_time
      - target_name, target_shift_type, target_date, target_time
      - requested_at, accepted_at, approved_at
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    PAGE_W, _ = A4
    USABLE_W = PAGE_W - 4 * cm

    styles = getSampleStyleSheet()
    elements: list = []

    # ── Styles ───────────────────────────────────────────
    s_ministry = ParagraphStyle(
        "Ministry", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=10, alignment=TA_CENTER,
        leading=13,
    )
    s_title = ParagraphStyle(
        "DocTitle", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=13, alignment=TA_CENTER,
        spaceAfter=4 * mm,
    )
    s_subtitle = ParagraphStyle(
        "SubTitle", parent=styles["Normal"],
        fontName="Helvetica", fontSize=9, alignment=TA_CENTER,
        textColor=colors.HexColor("#555555"),
        spaceAfter=6 * mm,
    )
    s_cell = ParagraphStyle(
        "Cell", parent=styles["Normal"],
        fontName="Helvetica", fontSize=7, alignment=TA_LEFT,
        leading=9,
    )
    s_cell_bold = ParagraphStyle(
        "CellBold", parent=s_cell,
        fontName="Helvetica-Bold",
    )
    s_footer = ParagraphStyle(
        "Footer", parent=styles["Normal"],
        fontName="Helvetica", fontSize=7, alignment=TA_CENTER,
        textColor=colors.HexColor("#666666"),
    )
    s_empty = ParagraphStyle(
        "Empty", parent=styles["Normal"],
        fontName="Helvetica-Oblique", fontSize=10, alignment=TA_CENTER,
        textColor=colors.HexColor("#999999"),
        spaceBefore=20 * mm,
    )

    # ── Header ───────────────────────────────────────────
    elements.append(Paragraph(
        "Ministério da Administração Interna<br/>"
        "<b>GUARDA NACIONAL REPUBLICANA</b>",
        s_ministry,
    ))
    elements.append(Paragraph(
        station_name,
        ParagraphStyle("StInfo", parent=styles["Normal"],
                        fontName="Helvetica", fontSize=9,
                        alignment=TA_CENTER, spaceAfter=4*mm),
    ))
    elements.append(Spacer(1, 4 * mm))

    # ── Title ────────────────────────────────────────────
    elements.append(Paragraph(
        '<u><b>RELATÓRIO DE TROCAS DE SERVIÇO</b></u>',
        s_title,
    ))
    elements.append(Paragraph(
        f"Período: {date_from.strftime('%d/%m/%Y')} a {date_to.strftime('%d/%m/%Y')}",
        s_subtitle,
    ))
    elements.append(Spacer(1, 4 * mm))

    if not swaps:
        elements.append(Paragraph(
            "Sem trocas aprovadas neste período.",
            s_empty,
        ))
    else:
        # ── Summary ──────────────────────────────────────
        elements.append(Paragraph(
            f"Total de trocas aprovadas: <b>{len(swaps)}</b>",
            ParagraphStyle("Summary", parent=styles["Normal"],
                            fontName="Helvetica", fontSize=10,
                            alignment=TA_LEFT, spaceAfter=4*mm),
        ))

        # ── Table ────────────────────────────────────────
        header = [
            Paragraph("<b>N.º</b>", s_cell_bold),
            Paragraph("<b>Declarante</b>", s_cell_bold),
            Paragraph("<b>Serviço</b>", s_cell_bold),
            Paragraph("<b>Data</b>", s_cell_bold),
            Paragraph("<b>Militar Alvo</b>", s_cell_bold),
            Paragraph("<b>Serviço</b>", s_cell_bold),
            Paragraph("<b>Data</b>", s_cell_bold),
            Paragraph("<b>Autorizada em</b>", s_cell_bold),
        ]

        rows = [header]
        for i, sw in enumerate(swaps, 1):
            rows.append([
                Paragraph(str(i), s_cell),
                Paragraph(sw["requester_name"], s_cell),
                Paragraph(sw["requester_shift_type"], s_cell),
                Paragraph(sw["requester_date"], s_cell),
                Paragraph(sw["target_name"], s_cell),
                Paragraph(sw["target_shift_type"], s_cell),
                Paragraph(sw["target_date"], s_cell),
                Paragraph(sw["approved_at"], s_cell),
            ])

        col_widths = [
            0.8 * cm,   # N.º
            USABLE_W * 0.17,  # Declarante
            USABLE_W * 0.12,  # Serviço
            USABLE_W * 0.11,  # Data
            USABLE_W * 0.17,  # Militar Alvo
            USABLE_W * 0.12,  # Serviço
            USABLE_W * 0.11,  # Data
            USABLE_W * 0.15,  # Autorizada em
        ]

        tbl = Table(rows, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")]),
        ]))
        elements.append(tbl)

    # ── Footer ───────────────────────────────────────────
    elements.append(Spacer(1, 10 * mm))
    today = date.today()
    elements.append(Paragraph(
        f"Documento gerado em {today.strftime('%d/%m/%Y')} · "
        f"Processado por computador · Guarda Nacional Republicana",
        s_footer,
    ))

    doc.build(elements)
    return buf.getvalue()


# ═════════════════════════════════════════════════════════
#  2. ESCALA MENSAL (landscape A4)
# ═════════════════════════════════════════════════════════

def generate_schedule_pdf(
    *,
    station_name: str,
    year: int,
    month: int,
    users: List[Dict[str, str]],
    shifts: List[Dict[str, Any]],
) -> bytes:
    """
    Generate a monthly schedule PDF in landscape A4.

    users: list of {"id": ..., "full_name": ..., "nip": ...}
    shifts: list of {
        "user_id": ...,
        "date": "YYYY-MM-DD",
        "shift_type_code": ...,
        "shift_type_color": ...,  (hex)
    }
    """
    buf = io.BytesIO()

    PAGE_W, PAGE_H = landscape(A4)
    L_MARGIN = 1.2 * cm
    R_MARGIN = 1.2 * cm
    T_MARGIN = 1.5 * cm
    B_MARGIN = 1.2 * cm
    USABLE_W = PAGE_W - L_MARGIN - R_MARGIN

    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=L_MARGIN,
        rightMargin=R_MARGIN,
        topMargin=T_MARGIN,
        bottomMargin=B_MARGIN,
    )

    styles = getSampleStyleSheet()
    elements: list = []

    month_name = _MESES[month]
    num_days = calendar.monthrange(year, month)[1]

    # ── Styles ───────────────────────────────────────────
    s_header = ParagraphStyle(
        "SchedHeader", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=9, alignment=TA_CENTER,
        leading=11,
    )
    s_title = ParagraphStyle(
        "SchedTitle", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=12, alignment=TA_CENTER,
        spaceAfter=2 * mm,
    )
    s_subtitle = ParagraphStyle(
        "SchedSub", parent=styles["Normal"],
        fontName="Helvetica", fontSize=8, alignment=TA_CENTER,
        textColor=colors.HexColor("#555555"),
        spaceAfter=4 * mm,
    )
    s_name_cell = ParagraphStyle(
        "NameCell", parent=styles["Normal"],
        fontName="Helvetica", fontSize=6, alignment=TA_LEFT,
        leading=8,
    )
    s_name_cell_header = ParagraphStyle(
        "NameCellHeader", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=6, alignment=TA_LEFT,
        leading=8, textColor=colors.white,
    )
    s_day_cell = ParagraphStyle(
        "DayCell", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=6, alignment=TA_CENTER,
        leading=8,
    )
    s_day_cell_header = ParagraphStyle(
        "DayCellHeader", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=6, alignment=TA_CENTER,
        leading=8, textColor=colors.white,
    )
    s_code_cell = ParagraphStyle(
        "CodeCell", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=6, alignment=TA_CENTER,
        leading=8,
    )
    s_footer = ParagraphStyle(
        "SchedFooter", parent=styles["Normal"],
        fontName="Helvetica", fontSize=6, alignment=TA_CENTER,
        textColor=colors.HexColor("#888888"),
    )

    # ── Header ───────────────────────────────────────────
    elements.append(Paragraph(
        "Ministério da Administração Interna · "
        "<b>GUARDA NACIONAL REPUBLICANA</b>",
        s_header,
    ))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        f'<u><b>ESCALA DE SERVIÇO — {month_name.upper()} {year}</b></u>',
        s_title,
    ))
    elements.append(Paragraph(
        station_name,
        s_subtitle,
    ))

    # ── Build shift lookup: { (user_id, day) -> code } ──
    shift_map: dict[tuple[str, int], str] = {}
    shift_color_map: dict[tuple[str, int], str] = {}
    for s in shifts:
        d = s["date"]
        if isinstance(d, str):
            day = int(d.split("-")[2])
        else:
            day = d.day
        key = (s["user_id"], day)
        shift_map[key] = s.get("shift_type_code") or ""
        shift_color_map[key] = s.get("shift_type_color") or ""

    # ── Column widths ────────────────────────────────────
    name_col_w = 3.8 * cm
    remaining_w = USABLE_W - name_col_w
    day_col_w = remaining_w / num_days
    col_widths = [name_col_w] + [day_col_w] * num_days

    # ── Header row (day numbers + weekday) ───────────────
    header_row = [Paragraph("<b>Militar</b>", s_name_cell_header)]
    weekend_cols: set[int] = set()
    for d in range(1, num_days + 1):
        dt_obj = date(year, month, d)
        wd = dt_obj.weekday()  # 0=Mon
        wd_label = _DIAS_SEMANA[wd]
        if wd >= 5:
            weekend_cols.add(d)
        header_row.append(Paragraph(
            f"<b>{d}</b><br/><font size='4'>{wd_label}</font>",
            s_day_cell_header,
        ))

    # ── Data rows ────────────────────────────────────────
    data_rows = [header_row]
    for u in users:
        row = [Paragraph(u["full_name"], s_name_cell)]
        for d in range(1, num_days + 1):
            key = (u["id"], d)
            code = shift_map.get(key, "")
            clr = shift_color_map.get(key, "")
            if code and clr:
                txt_color = "#ffffff" if _is_dark(clr) else "#1a202c"
                row.append(Paragraph(
                    f'<font color="{txt_color}">{code}</font>', s_code_cell
                ))
            else:
                row.append(Paragraph(code, s_code_cell))
        data_rows.append(row)

    # ── Build table ──────────────────────────────────────
    tbl = Table(data_rows, colWidths=col_widths, repeatRows=1)

    style_cmds: list = [
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a365d")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 6),
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        # Name column background
        ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#f7fafc")),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica"),
        # Alternating row colors
        ("ROWBACKGROUNDS", (1, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")]),
    ]

    # Weekend column shading
    for wd_col in weekend_cols:
        col_idx = wd_col  # offset by 1 for name col
        style_cmds.append(
            ("BACKGROUND", (col_idx, 1), (col_idx, len(users)),
             colors.HexColor("#fff5f5"))
        )

    # Color-code individual shift cells
    for row_idx, u in enumerate(users, 1):
        for d in range(1, num_days + 1):
            key = (u["id"], d)
            clr = shift_color_map.get(key)
            if clr:
                try:
                    bg = colors.HexColor(clr)
                    style_cmds.append(
                        ("BACKGROUND", (d, row_idx), (d, row_idx), bg)
                    )
                except Exception:
                    pass

    tbl.setStyle(TableStyle(style_cmds))
    elements.append(tbl)

    # ── Footer ───────────────────────────────────────────
    elements.append(Spacer(1, 4 * mm))
    today = date.today()
    elements.append(Paragraph(
        f"Gerado em {today.strftime('%d/%m/%Y')} · "
        f"Processado por computador · Guarda Nacional Republicana · "
        f"Página 1 de 1",
        s_footer,
    ))

    doc.build(elements)
    return buf.getvalue()
