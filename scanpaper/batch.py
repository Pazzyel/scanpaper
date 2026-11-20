"""Sequential batch export with independent settings and collision-safe names."""
from dataclasses import dataclass, field, replace
from pathlib import Path

from .model import Layout
from .pdf import export_pdf
from .processing import Cleanup, clean_image, load_jpeg, rotate_image


@dataclass
class Document:
    path: Path
    layout: Layout = field(default_factory=Layout)
    settings: Cleanup = field(default_factory=Cleanup)
    fitted: bool = False


@dataclass
class BatchResult:
    written: list = field(default_factory=list)
    failed: list = field(default_factory=list)


def reserve_destination(folder, stem):
    """Reserve a new name exclusively, including against concurrent writers."""
    number = 1
    while True:
        suffix = '' if number == 1 else f' ({number})'
        destination = folder / f'{stem}_清理{suffix}.pdf'
        try:
            with destination.open('xb'):
                pass
            return destination
        except FileExistsError:
            number += 1


def export_documents(documents, folder, progress=None):
    folder = Path(folder)
    if not folder.is_dir():
        raise NotADirectoryError(f'输出文件夹不存在：{folder}')
    result = BatchResult()
    for index, document in enumerate(documents, 1):
        destination = None
        try:
            # Decode one original at a time rather than retaining the whole batch.
            source = load_jpeg(document.path)
            try:
                layout = replace(document.layout)
                if not document.fitted:
                    aspect = source.width / source.height
                    layout.fit(1 / aspect if layout.rotation % 2 else aspect)
                cleaned = rotate_image(clean_image(source, document.settings), layout.rotation)
                try:
                    destination = reserve_destination(folder, document.path.stem)
                    export_pdf(cleaned, layout, destination)
                finally:
                    cleaned.close()
            finally:
                source.close()
            result.written.append(destination)
        except Exception as error:
            if destination is not None:
                try:
                    destination.unlink(missing_ok=True)
                except OSError as cleanup_error:
                    error = OSError(f'{error}；无法删除未完成的文件 {destination}：{cleanup_error}')
            # Keep the error type/message without retaining image arrays in worker frames.
            error.__traceback__ = None
            error.__context__ = None
            error.__cause__ = None
            result.failed.append((document.path, error))
        if progress is not None:
            progress((index, len(documents), document.path.name))
    return result
