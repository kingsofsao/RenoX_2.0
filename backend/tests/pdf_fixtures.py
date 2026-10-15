"""Generate problem PDFs (encrypted, scanned/image-only, blank) for tests."""

import io
from pathlib import Path

from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def encrypted_pdf(path: Path) -> Path:
    c = canvas.Canvas(str(path), pagesize=letter, encrypt="secret-password")
    c.drawString(72, 700, "Confidential paper text " * 20)
    c.showPage()
    c.save()
    return path


def scanned_pdf(path: Path) -> Path:
    """A page that is only a picture of text - what a scanner produces."""
    img = Image.new("RGB", (1200, 1600), "white")
    draw = ImageDraw.Draw(img)
    for i in range(30):
        draw.text((80, 80 + i * 45), "Scanned research paper line of text " * 2, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawImage(ImageReader(buf), 0, 0, width=letter[0], height=letter[1])
    c.showPage()
    c.save()
    return path


def blank_pdf(path: Path) -> Path:
    c = canvas.Canvas(str(path), pagesize=letter)
    c.showPage()
    c.save()
    return path


def untitled_pdf(path: Path) -> Path:
    """Body text only, all one font size: no reliable title or authors to detect."""
    c = canvas.Canvas(str(path), pagesize=letter)
    y = 740
    for i in range(40):
        c.setFont("Helvetica", 10)
        c.drawString(60, y, f"This report discusses results of experiment number {i} in some detail for testing.")
        y -= 16
    c.showPage()
    c.save()
    return path
