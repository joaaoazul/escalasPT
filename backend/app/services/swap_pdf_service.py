"""
PDF generation for approved shift swap requests.

Reproduces the official GNR "Troca de Serviço" form (Art. 34.º RGSGNR)
with data pre-filled from the system, including chronology timestamps.
"""

from __future__ import annotations

import io
import locale
from datetime import date, datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Portuguese month names (no system locale dependency) ──
_MESES = [
    "", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def _underline(text: str, width: int = 30) -> str:
    """Wrap text in an underline span for Paragraph."""
    return f'<u>{text}</u>'


def _blank_line(width: int = 30) -> str:
    return "_" * width


def generate_swap_pdf(
    *,
    swap_id: str,
    station_name: str,
    # Requester (O Declarante)
    requester_name: str,
    requester_shift_type: str,
    requester_shift_date: str,
    requester_start_time: str,
    requester_end_time: str,
    # Target (quem confirma)
    target_name: str,
    target_shift_type: str,
    target_shift_date: str,
    target_start_time: str,
    target_end_time: str,
    # Timestamps
    requested_at: str,
    accepted_at: str,
    approved_at: str,
) -> bytes:
    """Generate the official GNR swap form PDF and return raw bytes."""

    PAGE_W, PAGE_H = A4
    L_MARGIN = 2.5 * cm
    R_MARGIN = 2.5 * cm
    T_MARGIN = 2 * cm
    B_MARGIN = 2 * cm
    USABLE_W = PAGE_W - L_MARGIN - R_MARGIN

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=L_MARGIN,
        rightMargin=R_MARGIN,
        topMargin=T_MARGIN,
        bottomMargin=B_MARGIN,
    )

    styles = getSampleStyleSheet()
    elements: list = []

    # ── Styles ───────────────────────────────────────────
    s_ministry = ParagraphStyle(
        "Ministry", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=10, alignment=TA_CENTER,
        leading=13,
    )
    s_station_info = ParagraphStyle(
        "StationInfo", parent=styles["Normal"],
        fontName="Helvetica", fontSize=9, alignment=TA_LEFT,
        leading=12,
    )
    s_visto = ParagraphStyle(
        "Visto", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=11, alignment=TA_CENTER,
    )
    s_title = ParagraphStyle(
        "DocTitle", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=13, alignment=TA_CENTER,
        spaceAfter=6 * mm,
    )
    s_body = ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontName="Helvetica", fontSize=10, alignment=TA_LEFT,
        leading=18, spaceBefore=2 * mm,
    )
    s_body_center = ParagraphStyle(
        "BodyCenter", parent=s_body,
        alignment=TA_CENTER,
    )
    s_section = ParagraphStyle(
        "Section", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=11, alignment=TA_CENTER,
        spaceBefore=8 * mm, spaceAfter=4 * mm,
    )
    s_signature_label = ParagraphStyle(
        "SigLabel", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=10, alignment=TA_CENTER,
    )
    s_nota = ParagraphStyle(
        "Nota", parent=styles["Normal"],
        fontName="Helvetica", fontSize=8, alignment=TA_LEFT,
        leading=10, spaceBefore=2 * mm,
    )
    s_nota_bold = ParagraphStyle(
        "NotaBold", parent=s_nota,
        fontName="Helvetica-Bold",
    )
    s_footer = ParagraphStyle(
        "Footer", parent=styles["Normal"],
        fontName="Helvetica", fontSize=7, alignment=TA_CENTER,
        textColor=colors.HexColor("#666666"),
    )
    s_timestamp = ParagraphStyle(
        "Timestamp", parent=styles["Normal"],
        fontName="Helvetica", fontSize=8, alignment=TA_LEFT,
        leading=11, textColor=colors.HexColor("#444444"),
    )

    # ── Header: Ministry + GNR ───────────────────────────
    elements.append(Paragraph(
        "Ministério da Administração Interna<br/>"
        "<b>GUARDA NACIONAL REPUBLICANA</b>",
        s_ministry,
    ))
    elements.append(Spacer(1, 4 * mm))

    # Station info (left) + VISTO (right) in a table
    station_para = Paragraph(
        station_name,
        s_station_info,
    )
    visto_block = Paragraph("VISTO", s_visto)
    visto_line = Paragraph("_" * 22, ParagraphStyle(
        "VistoLine", parent=styles["Normal"],
        fontName="Helvetica", fontSize=9, alignment=TA_CENTER,
    ))

    header_table = Table(
        [[station_para, [visto_block, Spacer(1, 8 * mm), visto_line]]],
        colWidths=[USABLE_W * 0.6, USABLE_W * 0.4],
    )
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 8 * mm))

    # ── Title ────────────────────────────────────────────
    elements.append(Paragraph(
        '<u><b>TROCA DE SERVIÇO</b></u>',
        s_title,
    ))
    elements.append(Spacer(1, 4 * mm))

    # ── Body text (declaration) ──────────────────────────
    elements.append(Paragraph(
        f'Declaro que desejo efectuar uma troca de serviço de '
        f'<u>&nbsp;{requester_shift_type}&nbsp;</u> '
        f'no dia <u>&nbsp;{requester_shift_date}&nbsp;</u>, '
        f'no horário compreendido entre as <u>&nbsp;{requester_start_time}&nbsp;</u> '
        f'e as <u>&nbsp;{requester_end_time}&nbsp;</u>, com o/a',
        s_body,
    ))
    elements.append(Paragraph(
        f'<u>&nbsp;{target_name}&nbsp;</u>, '
        f'que se encontra de serviço de '
        f'<u>&nbsp;{target_shift_type}&nbsp;</u>, '
        f'no horário compreendido entre as <u>&nbsp;{target_start_time}&nbsp;</u> '
        f'e as <u>&nbsp;{target_end_time}&nbsp;</u>.',
        s_body,
    ))

    elements.append(Spacer(1, 10 * mm))

    # ── Location + date ──────────────────────────────────
    today = date.today()
    day_str = str(today.day)
    month_str = _MESES[today.month]
    year_str = str(today.year)

    # Extract location from "Posto Territorial de X" -> "X"
    location = station_name
    if location.lower().startswith("posto territorial de "):
        location = location[len("Posto Territorial de "):]

    elements.append(Paragraph(
        f'Quartel em {location}, '
        f'<u>&nbsp;{day_str}&nbsp;</u> de '
        f'<u>&nbsp;{month_str}&nbsp;</u> de '
        f'<u>&nbsp;{year_str}&nbsp;</u>',
        s_body,
    ))

    elements.append(Spacer(1, 10 * mm))

    # ── O DECLARANTE ─────────────────────────────────────
    elements.append(Paragraph("<b>O DECLARANTE</b>", s_body_center))
    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph(f'<i>{requester_name}</i>', s_body_center))
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph("_" * 40, s_body_center))

    elements.append(Spacer(1, 12 * mm))

    # ── CONFIRMO A TROCA ─────────────────────────────────
    elements.append(Paragraph("<b>CONFIRMO A TROCA</b>", s_section))
    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph(f'<i>{target_name}</i>', s_body_center))
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph("_" * 40, s_body_center))

    elements.append(Spacer(1, 10 * mm))

    # ── Cronologia (digital timestamps) ──────────────────
    elements.append(Paragraph(
        '<b>REGISTO DIGITAL</b>',
        ParagraphStyle("DigReg", parent=s_nota_bold, fontSize=9, spaceBefore=4*mm),
    ))
    elements.append(Spacer(1, 2 * mm))

    ts_data = [
        ["Pedido de troca:", requested_at],
        ["Aceitação pelo militar:", accepted_at],
        ["Autorização pelo Comandante:", approved_at],
    ]
    ts_table = Table(ts_data, colWidths=[5 * cm, 8 * cm])
    ts_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#333333")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(ts_table)

    elements.append(Spacer(1, 8 * mm))

    # ── Separator ────────────────────────────────────────
    sep = Table([[""]],  colWidths=[USABLE_W])
    sep.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
    ]))
    elements.append(sep)
    elements.append(Spacer(1, 3 * mm))

    # ── NOTA ─────────────────────────────────────────────
    elements.append(Paragraph("<b>NOTA:</b>", s_nota_bold))
    elements.append(Paragraph(
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        "Regulamento Geral do Serviço da Guarda Nacional Republicana",
        s_nota,
    ))
    elements.append(Paragraph(
        "Artigo 34.º (Trocas de serviço)",
        s_nota,
    ))
    elements.append(Paragraph(
        "1. São permitidas trocas de serviço entre militares da mesma escala, "
        "quando não acarretem prejuízo para o serviço, para a disciplina ou para terceiros.",
        s_nota,
    ))
    elements.append(Paragraph(
        "2. Os pedidos de troca são concedidos por motivos atendíveis e solicitados "
        "até à véspera da execução e sempre devidamente informado.",
        s_nota,
    ))
    elements.append(Paragraph(
        "5. Nas trocas de serviço observar-se-á o seguinte:",
        s_nota,
    ))
    elements.append(Paragraph(
        "&nbsp;&nbsp;&nbsp;c. O militar que troca um serviço fica obrigado a desempenhá-lo, "
        "sempre que seja possível, logo que este pertença ao militar com quem trocou.",
        s_nota,
    ))
    elements.append(Paragraph(
        "&nbsp;&nbsp;&nbsp;d. Quando o militar nomeado para o serviço por troca não o puder "
        "desempenhar, a responsabilidade da sua execução é do militar a quem, por escala, "
        "compete o serviço.",
        s_nota,
    ))

    # ── Footer ───────────────────────────────────────────
    elements.append(Spacer(1, 6 * mm))
    footer_data = [[
        Paragraph("Processado por computador", s_footer),
        Paragraph("Guarda Nacional Republicana", s_footer),
        Paragraph(f"Ref. {swap_id[:8].upper()} · Página 1 de 1", s_footer),
    ]]
    footer_table = Table(
        footer_data,
        colWidths=[USABLE_W / 3] * 3,
    )
    footer_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
    ]))
    elements.append(footer_table)

    # Build
    doc.build(elements)
    return buf.getvalue()
