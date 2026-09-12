import re
from datetime import date
from io import BytesIO
from xml.sax.saxutils import escape

import pymupdf as fitz
import pytesseract
from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .config import settings


def extract_identity(content: bytes):
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "Use a document smaller than 10 MB.")
    text = ""
    images = []
    if content.startswith(b"%PDF-"):
        try:
            with fitz.open(stream=content, filetype="pdf") as document:
                if document.is_encrypted or len(document) > 5:
                    raise HTTPException(422, "Use an unlocked PDF of up to five pages.")
                for page in document:
                    embedded = page.get_text()
                    if embedded.strip():
                        text += embedded + "\n"
                    else:
                        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                        if pix.width * pix.height > 20000000:
                            raise HTTPException(422, "Image resolution is too large.")
                        images.append(Image.open(BytesIO(pix.tobytes("png"))))
        except (fitz.FileDataError, RuntimeError):
            raise HTTPException(422, "This PDF cannot be read. Use manual entry.") from None
    else:
        try:
            image = Image.open(BytesIO(content))
            if image.format not in {"JPEG", "PNG"} or image.width * image.height > 20000000:
                raise HTTPException(422, "Use a JPG/PNG with at most 20 million pixels.")
            image.load()
            images.append(image)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise HTTPException(422, "This is not a readable JPG, PNG or PDF.") from None
    if images:
        if settings().tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings().tesseract_cmd
        try:
            for image in images:
                text += pytesseract.image_to_string(image, timeout=20) + "\n"
        except (pytesseract.TesseractNotFoundError, RuntimeError):
            raise HTTPException(503, "Local image OCR is unavailable. Enter your details manually.") from None
        finally:
            for image in images:
                image.close()
    values = {}
    for key, pattern in {
        "legal_name": r"(?:Full name|Name)\s*[:\-]\s*([^\n]+)",
        "nationality": r"Nationality\s*[:\-]\s*([^\n]+)",
    }.items():
        found = re.search(pattern, text, re.IGNORECASE)
        if found:
            values[key] = found.group(1).strip()[:250]
    born = re.search(r"(?:Date of birth|DOB)\s*[:\-]\s*(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
    if born:
        try:
            parsed = date.fromisoformat(born.group(1))
            if date(1900, 1, 1) <= parsed < date.today():
                values["date_of_birth"] = parsed.isoformat()
        except ValueError:
            pass
    # TD3 MRZ names are provisional. Do not treat parsing/check digits as document authentication.
    lines = [line.replace(" ", "").strip() for line in text.splitlines()]
    for line in lines:
        if line.startswith("P<") and len(line) == 44 and "<<" in line[5:]:
            surname, given = line[5:].split("<<", 1)
            values.setdefault(
                "legal_name", " ".join((given.replace("<", " ") + " " + surname.replace("<", " ")).split())
            )
    return {
        "fields": values,
        "status": "needs_review" if values else "manual_entry_required",
        "notice": "Check every extracted field. This is text extraction, not identity verification. Raw file discarded.",
    }


def quotation_pdf(snapshot, quote_id):
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    story = [
        Paragraph("HELM AI / INDICATIVE QUOTATION", styles["Title"]),
        Spacer(1, 16),
        Paragraph("Fictional demonstration. This is not issued insurance cover.", styles["Normal"]),
        Paragraph(escape(f"Reference: {quote_id}"), styles["Normal"]),
        Paragraph(escape(f"Applicant: {snapshot['applicant_name']}"), styles["Normal"]),
        Paragraph(escape(f"Created: {snapshot['generated_at']} | Validity: not supplied"), styles["Normal"]),
        Spacer(1, 20),
    ]
    rows = [["Plan", "Annual AED", "Deductible", "Copay", "Annual limit"]]
    for item in snapshot["items"]:
        p = item["plan"]
        rows.append(
            [
                p["name"],
                f"{p['annual_premium']:,}",
                f"{p['deductible']:,}",
                f"{p['outpatient_copay_pct']}%",
                f"{p['annual_limit']:,}",
            ]
        )
    table = Table(rows, repeatRows=1, colWidths=[110, 95, 90, 65, 100])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#000b33")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ]
        )
    )
    story += [table, Spacer(1, 20)]
    for item in snapshot["items"]:
        p = item["plan"]
        story.append(
            Paragraph(escape(p["name"] + " — " + item["status"].replace("_", " ")), styles["Heading2"])
        )
        maternity = p["maternity"]
        chronic = p["chronic_preexisting"]
        terms = [
            f"Network: {p['network_note']}",
            f"Maternity: {str(maternity)}",
            f"Existing conditions: {str(chronic)}",
            f"Dental/optical: {p['dental_optical']}",
        ]
        for text in terms + item["reasons"] + item["gaps"] + item["unknowns"]:
            story.append(Paragraph(escape(text), styles["Normal"]))
        story.append(Spacer(1, 10))
    story.append(
        Paragraph(
            "Source: supplied fictional challenge catalogue v3. No real insurer contact or instalment offer is represented. Monthly figures in the app are budget equivalents; sandbox schedules are simulations.",
            styles["Normal"],
        )
    )
    SimpleDocTemplate(buffer, title="Helm AI indicative quotation", author="Helm AI").build(story)
    return buffer.getvalue()
