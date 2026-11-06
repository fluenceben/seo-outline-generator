import io

from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.shared import RGBColor

MAX_KEYWORD_ROWS = 15
NEW_HEADER_COLOR = RGBColor(0xC0, 0x39, 0x2B)


def build_docx(title, h1, primary_keyword, secondary_keywords, client_url, outline_rows, faqs, tfidf_terms):
    doc = Document()

    doc.add_heading(title or primary_keyword or "Content Outline", level=0)

    meta_parts = [f"Primary keyword: {primary_keyword}"]
    if secondary_keywords:
        meta_parts.append(f"Secondary keywords: {secondary_keywords}")
    if client_url:
        meta_parts.append(f"Client: {client_url}")
    meta = doc.add_paragraph()
    meta.add_run(" | ".join(meta_parts)).italic = True

    doc.add_heading(h1 or primary_keyword, level=1)

    for row in outline_rows:
        level_str = row.get("level", "H2")
        try:
            level = int(str(level_str).replace("H", ""))
        except ValueError:
            level = 2
        level = max(2, min(4, level))
        heading = doc.add_heading(row.get("text", ""), level=level)
        if row.get("is_new"):
            for run in heading.runs:
                run.font.color.rgb = NEW_HEADER_COLOR
                run.font.highlight_color = WD_COLOR_INDEX.YELLOW
            badge = heading.add_run("  [NEW]")
            badge.bold = True
            badge.font.color.rgb = NEW_HEADER_COLOR

    if faqs:
        doc.add_heading("FAQs", level=2)
        for question in faqs:
            p = doc.add_paragraph()
            p.add_run(question).bold = True

    usable_terms = [t for t in tfidf_terms if t.get("max_uses")][:MAX_KEYWORD_ROWS]
    if usable_terms:
        doc.add_heading("Keyword usage targets", level=2)
        doc.add_paragraph(
            "Based on how many times competitors ranking for this keyword used each term."
        )
        table = doc.add_table(rows=1, cols=2)
        table.style = "Table Grid"
        header_cells = table.rows[0].cells
        header_cells[0].text = "Term"
        header_cells[1].text = "Target uses"
        for term in usable_terms:
            cells = table.add_row().cells
            cells[0].text = term.get("term", "")
            cells[1].text = f"{term.get('min_uses', 0)}-{term.get('max_uses', 0)}"

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
