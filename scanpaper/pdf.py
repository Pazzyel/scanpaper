import os
from pathlib import Path
import tempfile

from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from .model import PT_PER_MM
from . import __version__


def export_pdf(image, layout, destination):
    export_pages(((image, layout),), destination)


def export_pages(pages, destination):
    """Write beside the destination; replace it only after a complete PDF exists."""
    destination = Path(destination)
    handle, temporary = tempfile.mkstemp(prefix=".scanpaper-", suffix=".pdf", dir=destination.parent)
    os.close(handle)
    try:
        canvas = Canvas(temporary, pageCompression=1, pdfVersion=(1, 4))
        canvas.setTitle(destination.stem)
        canvas.setCreator(f"ScanPaper {__version__}")
        page_count = 0
        for image, layout in pages:
            layout.validate()
            paper_width, paper_height = layout.paper_size
            page_size = (paper_width * PT_PER_MM, paper_height * PT_PER_MM)
            canvas.setPageSize(page_size)
            canvas.saveState()
            clip = canvas.beginPath()
            clip.rect(0, 0, *page_size)
            canvas.clipPath(clip, stroke=0, fill=0)
            canvas.drawImage(ImageReader(image), layout.x * PT_PER_MM,
                             (paper_height - layout.y - layout.height) * PT_PER_MM,
                             layout.width * PT_PER_MM, layout.height * PT_PER_MM, mask="auto")
            canvas.restoreState()
            canvas.showPage()
            page_count += 1
        if not page_count:
            raise ValueError("请至少导入一张图片")
        canvas.save()
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

