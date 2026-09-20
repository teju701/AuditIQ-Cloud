from fpdf import FPDF
from fpdf.enums import XPos, YPos
from datetime import datetime
import pandas as pd

def safe_text(text) -> str:
    if not isinstance(text, str):
        text = str(text)

    replacements = {
        "—": "-",
        "–": "-",
        "“": '"',
        "”": '"',
        "’": "'",
        "\u00a0": " ",  # non-breaking space
    }

    for k, v in replacements.items():
        text = text.replace(k, v)

    return text.encode("latin-1", "ignore").decode("latin-1")


def write_line(pdf: FPDF, text: str, height: float = 6, char_wrap: bool = False) -> None:
    kwargs = {
        "new_x": XPos.LMARGIN,
        "new_y": YPos.NEXT,
    }
    if char_wrap:
        kwargs["wrapmode"] = "CHAR"
    pdf.multi_cell(0, height, safe_text(text), **kwargs)

def export_finding_pdf(
    query: str,
    narrative: str,
    logic: str,
    trust: dict,
    df_result: pd.DataFrame | None,
    replay_id: str | None = None,
    reproducibility: dict | None = None,
    provenance: dict | None = None,
    narrative_grounding: dict | None = None,
    consensus: dict | None = None,
) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    # Header
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, safe_text("AuditIQ - Audit Finding Report"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)

    # Trust score
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, safe_text(f"Trust Score: {trust['level']} ({trust['score']}/100)"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    for reason in trust["reasons"]:
        write_line(pdf, f"  - {reason}", 6)
    pdf.ln(4)

    # Query
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Auditor Query", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    write_line(pdf, query, 6)
    pdf.ln(4)

    # Answer
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Finding Summary", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    write_line(pdf, narrative, 6)
    pdf.ln(4)

    # Logic
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Filter Logic Applied", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Courier", "", 9)
    write_line(pdf, logic, 5, char_wrap=True)
    pdf.ln(4)

    # Reproducibility
    if replay_id or reproducibility:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Reproducibility", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Courier", "", 8)

        if replay_id:
            write_line(pdf, f"Replay ID: {replay_id}", 5, char_wrap=True)

        if reproducibility:
            lines = [
                f"Dataset ID: {reproducibility.get('dataset_id', '')}",
                f"Dataset Hash: {reproducibility.get('dataset_hash', '')}",
                f"Normalized Query: {reproducibility.get('normalized_query', '')}",
                f"Query Hash: {reproducibility.get('query_hash', '')}",
                f"Plan Hash: {reproducibility.get('plan_hash', '')}",
                f"Execution Mode: {reproducibility.get('execution_mode', '')}",
                f"Row Count: {reproducibility.get('row_count', '')}",
                f"Generated At (UTC): {reproducibility.get('generated_at', '')}",
            ]
            for line in lines:
                write_line(pdf, line, 5, char_wrap=True)
        pdf.ln(3)

    # Provenance
    if provenance:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Evidence Provenance", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Courier", "", 8)

        lineage = provenance.get("lineage", {}) if isinstance(provenance.get("lineage"), dict) else {}
        lines = [
            f"Intent: {provenance.get('intent', '')}",
            f"Execution Mode: {provenance.get('execution_mode', '')}",
            f"Input Rows: {provenance.get('input_rows', '')}",
            f"Output Rows: {provenance.get('output_rows', '')}",
            f"Evidence Coverage %: {provenance.get('evidence_coverage_pct', '')}",
            f"Lineage Filters: {lineage.get('filters', [])}",
            f"Lineage Group By: {lineage.get('group_by', [])}",
            f"Lineage Aggregations: {lineage.get('aggregations', [])}",
            f"Lineage Sort: {lineage.get('sort', [])}",
            f"Lineage Limit: {lineage.get('limit', '')}",
        ]
        for line in lines:
            write_line(pdf, line, 5, char_wrap=True)
        pdf.ln(3)

    # Narrative grounding
    if narrative_grounding:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Narrative Grounding", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Courier", "", 8)

        status = narrative_grounding.get("status", "unknown")
        write_line(pdf, f"Status: {status}", 5)
        for issue in narrative_grounding.get("issues", []):
            write_line(pdf, f"Issue: {issue}", 5)
        for claim in narrative_grounding.get("verified_claims", []):
            write_line(pdf, f"Verified: {claim}", 5)
        pdf.ln(3)

    # Consensus
    if consensus:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Dual-Run Consensus", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Courier", "", 8)

        lines = [
            f"Enabled: {consensus.get('enabled', False)}",
            f"Status: {consensus.get('status', '')}",
            f"Score: {consensus.get('score', '')}",
            f"Reason: {consensus.get('reason', '')}",
            f"Plan Match: {consensus.get('plan_match', '')}",
            f"Plan Similarity %: {consensus.get('plan_similarity_pct', '')}",
            f"Row Overlap %: {consensus.get('row_overlap_pct', '')}",
            f"Row Count Similarity %: {consensus.get('row_count_similarity_pct', '')}",
        ]

        for line in lines:
            write_line(pdf, line, 5, char_wrap=True)
        pdf.ln(3)

    # Evidence table
    if df_result is not None and len(df_result) > 0:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, safe_text(f"Evidence - {min(len(df_result), 20)} matching records"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 7)

        cols = list(df_result.columns)[:6]
        col_width = 160 / len(cols)

        pdf.set_fill_color(230, 230, 230)
        for col in cols:
            pdf.cell(col_width, 6, safe_text(str(col)[:18]), border=1, fill=True)
        pdf.ln()

        for _, row in df_result.head(20).iterrows():
            for col in cols:
                pdf.cell(col_width, 5, safe_text(str(row[col])[:18]), border=1)
            pdf.ln()

    return bytes(pdf.output())