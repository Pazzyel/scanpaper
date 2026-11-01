import os
from pathlib import Path
import tempfile

from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from .model import PT_PER_MM


def export_pdf(image, layout, destination):
    """Write beside the destination; replace it only after a complete PDF exists."""
    layout.validate()
    destination = Path(destination)
    pw, ph = layout.paper_size
    handle, temporary = tempfile.mkstemp(prefix=".scanpaper-", suffix=".pdf", dir=destination.parent)
    os.close(handle)
    try:
        canvas = Canvas(temporary, pagesize=(pw * PT_PER_MM, ph * PT_PER_MM),
                        pageCompression=1, pdfVersion=(1, 4))
        canvas.setTitle(destination.stem)
        canvas.setCreator("ScanPaper 1.0")
        canvas.saveState()
        clip = canvas.beginPath()
        clip.rect(0, 0, pw * PT_PER_MM, ph * PT_PER_MM)
        canvas.clipPath(clip, stroke=0, fill=0)
        canvas.drawImage(ImageReader(image), layout.x * PT_PER_MM,
                         (ph - layout.y - layout.height) * PT_PER_MM,
                         layout.width * PT_PER_MM, layout.height * PT_PER_MM, mask="auto")
        canvas.restoreState()
        canvas.showPage()
        canvas.save()
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

