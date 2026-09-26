package pt.turnos.swaps.internal;

import java.awt.Color;
import java.io.ByteArrayOutputStream;
import java.time.LocalDate;

import org.openpdf.text.Chunk;
import org.openpdf.text.Document;
import org.openpdf.text.Element;
import org.openpdf.text.Font;
import org.openpdf.text.PageSize;
import org.openpdf.text.Paragraph;
import org.openpdf.text.Phrase;
import org.openpdf.text.Rectangle;
import org.openpdf.text.pdf.BaseFont;
import org.openpdf.text.pdf.PdfPCell;
import org.openpdf.text.pdf.PdfPTable;
import org.openpdf.text.pdf.PdfWriter;
import org.openpdf.text.pdf.draw.LineSeparator;

/**
 * Formulário oficial "Troca de Serviço" (Art. 34.º do RGSGNR), reproduzido a partir do swap_pdf_service.py do EscalasPT:
 * A4, margens 2,5 cm laterais e 2 cm em cima e em baixo, Helvetica, os mesmos textos, tamanhos e espaçamentos.
 * Diferenças: sai a linha "Autorização pelo Comandante" do registo digital, e o rodapé indica a página real.
 */
final class SwapForm {

    /** Dados impressos, já formatados (datas dd/MM/yyyy, horas HH:mm, carimbos "dd/MM/yyyy às HH:mm"). */
    record Data(String reference, String stationName, String location, LocalDate issuedOn,
                String requesterName, String requesterShiftType, String requesterShiftDate, String requesterStart, String requesterEnd,
                String targetName, String targetShiftType, String targetStart, String targetEnd,
                String requestedAt, String acceptedAt) {
    }

    private static final String[] MESES = {"", "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
            "setembro", "outubro", "novembro", "dezembro"};
    private static final float MM = 72f / 25.4f;
    private static final float CM = 10 * MM;

    private SwapForm() {
    }

    static byte[] render(Data d) {
        try {
            BaseFont regular = BaseFont.createFont(BaseFont.HELVETICA, BaseFont.CP1252, BaseFont.NOT_EMBEDDED);
            BaseFont bold = BaseFont.createFont(BaseFont.HELVETICA_BOLD, BaseFont.CP1252, BaseFont.NOT_EMBEDDED);
            BaseFont italic = BaseFont.createFont(BaseFont.HELVETICA_OBLIQUE, BaseFont.CP1252, BaseFont.NOT_EMBEDDED);

            ByteArrayOutputStream out = new ByteArrayOutputStream();
            Document doc = new Document(PageSize.A4, 2.5f * CM, 2.5f * CM, 2 * CM, 2 * CM);
            PdfWriter writer = PdfWriter.getInstance(doc, out);
            doc.addTitle("Troca de Serviço");
            doc.addCreator("Turnos");
            doc.open();
            float usable = PageSize.A4.getWidth() - 5 * CM;

            // Cabeçalho: Ministério + GNR
            Paragraph ministry = new Paragraph(13, "Ministério da Administração Interna\nGUARDA NACIONAL REPUBLICANA", new Font(bold, 10));
            ministry.setAlignment(Element.ALIGN_CENTER);
            doc.add(ministry);
            doc.add(spacer(4));

            // Posto (esquerda) + VISTO (direita)
            PdfPTable header = new PdfPTable(new float[] {0.6f, 0.4f});
            header.setTotalWidth(usable);
            header.setLockedWidth(true);
            header.addCell(cell(new Paragraph(12, d.stationName(), new Font(regular, 9)), Element.ALIGN_LEFT));
            PdfPCell visto = cell(null, Element.ALIGN_CENTER);
            Paragraph v = new Paragraph("VISTO", new Font(bold, 11));
            v.setAlignment(Element.ALIGN_CENTER);
            visto.addElement(v);
            visto.addElement(spacer(8));
            Paragraph vl = new Paragraph("_".repeat(22), new Font(regular, 9));
            vl.setAlignment(Element.ALIGN_CENTER);
            visto.addElement(vl);
            header.addCell(visto);
            doc.add(header);
            doc.add(spacer(8));

            // Título
            Chunk title = new Chunk("TROCA DE SERVIÇO", new Font(bold, 13));
            title.setUnderline(0.8f, -2f);
            Paragraph t = new Paragraph(title);
            t.setAlignment(Element.ALIGN_CENTER);
            t.setSpacingAfter(6 * MM);
            doc.add(t);
            doc.add(spacer(4));

            // Declaração
            Font body = new Font(regular, 10);
            doc.add(bodyParagraph(body,
                    "Declaro que desejo efectuar uma troca de serviço de ", u(d.requesterShiftType(), body),
                    " no dia ", u(d.requesterShiftDate(), body),
                    ", no horário compreendido entre as ", u(d.requesterStart(), body),
                    " e as ", u(d.requesterEnd(), body), ", com o/a"));
            doc.add(bodyParagraph(body,
                    u(d.targetName(), body), ", que se encontra de serviço de ", u(d.targetShiftType(), body),
                    ", no horário compreendido entre as ", u(d.targetStart(), body),
                    " e as ", u(d.targetEnd(), body), "."));
            doc.add(spacer(10));

            // Local e data
            LocalDate on = d.issuedOn();
            doc.add(bodyParagraph(body, "Quartel em " + d.location() + ", ", u(String.valueOf(on.getDayOfMonth()), body), " de ",
                    u(MESES[on.getMonthValue()], body), " de ", u(String.valueOf(on.getYear()), body)));
            doc.add(spacer(10));

            // O DECLARANTE
            doc.add(centered("O DECLARANTE", new Font(bold, 10), 18, 2 * MM, 0));
            doc.add(spacer(6));
            doc.add(centered(d.requesterName(), new Font(italic, 10), 18, 2 * MM, 0));
            doc.add(spacer(3));
            doc.add(centered("_".repeat(40), body, 18, 2 * MM, 0));
            doc.add(spacer(12));

            // CONFIRMO A TROCA
            doc.add(centered("CONFIRMO A TROCA", new Font(bold, 11), 13.2f, 8 * MM, 4 * MM));
            doc.add(spacer(6));
            doc.add(centered(d.targetName(), new Font(italic, 10), 18, 2 * MM, 0));
            doc.add(spacer(3));
            doc.add(centered("_".repeat(40), body, 18, 2 * MM, 0));
            doc.add(spacer(10));

            // Registo digital (sem a linha "Autorização pelo Comandante")
            Paragraph reg = new Paragraph(10, "REGISTO DIGITAL", new Font(bold, 9));
            reg.setSpacingBefore(4 * MM);
            doc.add(reg);
            doc.add(spacer(2));
            Color grey = new Color(0x33, 0x33, 0x33);
            PdfPTable ts = new PdfPTable(new float[] {5, 8});
            ts.setTotalWidth(13 * CM);
            ts.setLockedWidth(true);
            ts.setHorizontalAlignment(Element.ALIGN_CENTER); // como no reportlab (hAlign por omissão)
            for (String[] row : new String[][] {{"Pedido de troca:", d.requestedAt()}, {"Aceitação pelo militar:", d.acceptedAt()}}) {
                ts.addCell(tsCell(row[0], new Font(bold, 8, Font.NORMAL, grey)));
                ts.addCell(tsCell(row[1], new Font(regular, 8, Font.NORMAL, grey)));
            }
            doc.add(ts);
            doc.add(spacer(8));

            // Separador
            LineSeparator line = new LineSeparator(0.5f, 100, new Color(0x99, 0x99, 0x99), Element.ALIGN_CENTER, 0);
            doc.add(new Chunk(line));
            doc.add(spacer(3));

            // NOTA
            Font nota = new Font(regular, 8);
            doc.add(notaParagraph(new Phrase("NOTA:", new Font(bold, 8))));
            doc.add(notaParagraph(new Phrase(" ".repeat(8) + "Regulamento Geral do Serviço da Guarda Nacional Republicana", nota)));
            doc.add(notaParagraph(new Phrase("Artigo 34.º (Trocas de serviço)", nota)));
            doc.add(notaParagraph(new Phrase("1. São permitidas trocas de serviço entre militares da mesma escala, "
                    + "quando não acarretem prejuízo para o serviço, para a disciplina ou para terceiros.", nota)));
            doc.add(notaParagraph(new Phrase("2. Os pedidos de troca são concedidos por motivos atendíveis e solicitados "
                    + "até à véspera da execução e sempre devidamente informado.", nota)));
            doc.add(notaParagraph(new Phrase("5. Nas trocas de serviço observar-se-á o seguinte:", nota)));
            doc.add(notaParagraph(new Phrase("   c. O militar que troca um serviço fica obrigado a desempenhá-lo, "
                    + "sempre que seja possível, logo que este pertença ao militar com quem trocou.", nota)));
            doc.add(notaParagraph(new Phrase("   d. Quando o militar nomeado para o serviço por troca não o puder "
                    + "desempenhar, a responsabilidade da sua execução é do militar a quem, por escala, compete o serviço.", nota)));

            // Rodapé
            doc.add(spacer(6));
            Font foot = new Font(regular, 7, Font.NORMAL, new Color(0x66, 0x66, 0x66));
            PdfPTable footer = new PdfPTable(3);
            footer.setTotalWidth(usable);
            footer.setLockedWidth(true);
            footer.addCell(cell(new Paragraph("Processado por computador", foot), Element.ALIGN_LEFT));
            footer.addCell(cell(new Paragraph("Guarda Nacional Republicana", foot), Element.ALIGN_CENTER));
            // O rodapé é o último elemento: a página em que cai é a última. (O EscalasPT escrevia sempre "Página 1 de 1",
            // mas o formulário ocupa duas páginas, com a NOTA na segunda.)
            int page = writer.getPageNumber();
            footer.addCell(cell(new Paragraph("Ref. " + d.reference() + " · Página " + page + " de " + page, foot), Element.ALIGN_RIGHT));
            doc.add(footer);

            doc.close();
            return out.toByteArray();
        } catch (Exception e) {
            throw new IllegalStateException("Falha a gerar o documento de troca", e);
        }
    }

    private static Chunk u(String text, Font f) {
        Chunk c = new Chunk(" " + text + " ", f);
        c.setUnderline(0.5f, -1.5f);
        return c;
    }

    private static Paragraph bodyParagraph(Font f, Object... parts) {
        Paragraph p = new Paragraph(18);
        p.setFont(f);
        p.setSpacingBefore(2 * MM);
        for (Object o : parts) {
            p.add(o instanceof Chunk c ? c : new Chunk(o.toString(), f));
        }
        return p;
    }

    private static Paragraph centered(String text, Font f, float leading, float before, float after) {
        Paragraph p = new Paragraph(leading, text, f);
        p.setAlignment(Element.ALIGN_CENTER);
        p.setSpacingBefore(before);
        p.setSpacingAfter(after);
        return p;
    }

    private static Paragraph notaParagraph(Phrase phrase) {
        Paragraph p = new Paragraph(10);
        p.add(phrase);
        p.setSpacingBefore(2 * MM);
        return p;
    }

    /** Espaço vertical exato, como o Spacer do reportlab (um parágrafo vazio acrescentaria a entrelinha). */
    private static PdfPTable spacer(float mm) {
        PdfPTable t = new PdfPTable(1);
        t.setWidthPercentage(100);
        PdfPCell c = new PdfPCell();
        c.setBorder(Rectangle.NO_BORDER);
        c.setFixedHeight(mm * MM);
        t.addCell(c);
        return t;
    }

    private static PdfPCell cell(Paragraph content, int align) {
        PdfPCell c = new PdfPCell();
        c.setBorder(Rectangle.NO_BORDER);
        c.setPadding(0);
        c.setHorizontalAlignment(align);
        c.setVerticalAlignment(Element.ALIGN_TOP);
        if (content != null) {
            content.setAlignment(align);
            c.addElement(content);
        }
        return c;
    }

    private static PdfPCell tsCell(String text, Font f) {
        PdfPCell c = new PdfPCell(new Phrase(text, f));
        c.setBorder(Rectangle.NO_BORDER);
        c.setPaddingTop(2);
        c.setPaddingBottom(2);
        c.setPaddingLeft(0);
        c.setVerticalAlignment(Element.ALIGN_MIDDLE);
        return c;
    }
}
