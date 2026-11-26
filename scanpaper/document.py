from contextlib import closing
from dataclasses import dataclass, field, replace
from pathlib import Path

from .model import Layout
from .pdf import export_pages
from .processing import Cleanup, clean_image, load_jpeg, rotate_image


@dataclass
class Document:
    path: Path
    layout: Layout = field(default_factory=Layout)
    settings: Cleanup = field(default_factory=Cleanup)
    fitted: bool = False


def document_pages(documents, progress):
    for number, document in enumerate(documents, 1):
        layout = replace(document.layout)
        try:
            with closing(load_jpeg(document.path)) as source:
                if not document.fitted:
                    layout.fit(source.width / source.height)
                cleaned = rotate_image(clean_image(source, document.settings), layout.rotation)
        except Exception as error:
            raise ValueError(f'第 {number} 页（{document.path.name}）处理失败：{error}') from error
        with closing(cleaned):
            yield cleaned, layout
        if progress is not None:
            progress(number)


def export_documents(documents, destination, progress=None):
    with closing(document_pages(documents, progress)) as pages:
        export_pages(pages, destination)
