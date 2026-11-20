import gc
import tempfile
from pathlib import Path
import unittest
import weakref
from unittest.mock import patch

from PIL import Image, ImageDraw
import numpy as np
from pypdf import PdfReader

from scanpaper.batch import Document, export_documents
from scanpaper.model import Layout, PT_PER_MM
from scanpaper.processing import Cleanup


class BatchTests(unittest.TestCase):
    def make_image(self, path, size=(120, 180)):
        image = Image.new('RGB', size, 'white')
        ImageDraw.Draw(image).rectangle((10, 10, 40, 40), fill='black')
        image.save(path)
        return Document(path)

    def test_separate_pdfs_keep_resolution_and_fit_each_aspect(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            documents = [self.make_image(folder / '竖图.jpg'),
                         self.make_image(folder / '横图.JPG', (240, 120))]
            documents[1].layout = Layout(paper='A3', landscape=True)
            progress = []
            result = export_documents(documents, folder, progress.append)
            self.assertEqual(len(result.written), 2)
            self.assertEqual(result.failed, [])
            self.assertEqual([entry[:2] for entry in progress], [(1, 2), (2, 2)])
            for document, path, size in zip(documents, result.written, [(120, 180), (240, 120)]):
                pdf = PdfReader(path)
                self.assertEqual(len(pdf.pages), 1)
                page = pdf.pages[0]
                self.assertAlmostEqual(float(page.mediabox.width), document.layout.paper_size[0] * PT_PER_MM, places=3)
                resource = next(iter(page['/Resources']['/XObject'].values())).get_object()
                self.assertEqual((resource['/Width'], resource['/Height']), size)
                transform = [args for args, op in page.get_contents().operations if op == b'cm'][-1]
                width, height = float(transform[0]), float(transform[3])
                self.assertAlmostEqual(width / height, size[0] / size[1], places=4)
                self.assertGreaterEqual(float(transform[4]), 10 * PT_PER_MM - 0.001)
            self.assertFalse(documents[0].fitted)

    def test_existing_files_and_duplicate_stems_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            first = self.make_image(folder / '扫描.jpg')
            second = self.make_image(folder / '扫描.jpeg')
            existing = folder / '扫描_清理.pdf'
            existing.write_bytes(b'keep original')
            result = export_documents([first, second], folder)
            self.assertEqual(existing.read_bytes(), b'keep original')
            self.assertEqual([path.name for path in result.written], ['扫描_清理 (2).pdf', '扫描_清理 (3).pdf'])

    def test_broken_image_and_failed_write_do_not_stop_remaining_images(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            first = self.make_image(folder / 'first.jpg')
            broken = folder / 'broken.jpg'
            broken.write_bytes(b'broken jpeg')
            last = self.make_image(folder / 'last.jpg')
            from scanpaper.pdf import export_pdf
            def write(image, layout, path):
                if path.stem.startswith('first'):
                    raise PermissionError('locked')
                export_pdf(image, layout, path)
            progress = []
            with patch('scanpaper.batch.export_pdf', side_effect=write):
                result = export_documents([first, Document(broken), last], folder, progress.append)
            self.assertEqual([path.name for path in result.written], ['last_清理.pdf'])
            self.assertEqual([path.name for path, error in result.failed], ['first.jpg', 'broken.jpg'])
            self.assertFalse((folder / 'first_清理.pdf').exists())
            self.assertEqual(len(progress), 3)
            self.assertEqual(list(folder.glob('.scanpaper-*')), [])

    def test_individual_layout_rotation_and_cleanup_are_used(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            document = self.make_image(folder / 'rotated.jpg')
            document.layout = Layout(paper='A2', x=23, y=31, width=150, height=100, rotation=1)
            document.settings = Cleanup(12, 78)
            document.fitted = True
            from scanpaper.processing import clean_image
            with patch('scanpaper.batch.clean_image', wraps=clean_image) as cleanup:
                result = export_documents([document], folder)
            self.assertEqual(result.failed, [])
            self.assertEqual(cleanup.call_args.args[1], Cleanup(12, 78))
            page = PdfReader(result.written[0]).pages[0]
            resource = next(iter(page['/Resources']['/XObject'].values())).get_object()
            self.assertEqual((resource['/Width'], resource['/Height']), (180, 120))
            transform = [args for args, op in page.get_contents().operations if op == b'cm'][-1]
            self.assertAlmostEqual(float(transform[0]), 150 * PT_PER_MM, places=3)
            self.assertAlmostEqual(float(transform[4]), 23 * PT_PER_MM, places=3)

    def test_failed_processing_releases_intermediate_arrays_before_continuing(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            documents = [self.make_image(folder / f'{index}.jpg') for index in range(3)]
            arrays = []
            from scanpaper.processing import clean_image
            def cleanup(image, settings):
                if len(arrays) < 2:
                    intermediate = np.ones((256, 256))
                    arrays.append(weakref.ref(intermediate))
                    raise MemoryError('simulated processing failure')
                return clean_image(image, settings)
            def progress(value):
                gc.collect()
                self.assertTrue(all(reference() is None for reference in arrays))
            with patch('scanpaper.batch.clean_image', side_effect=cleanup):
                result = export_documents(documents, folder, progress)
            self.assertEqual(len(result.written), 1)
            self.assertEqual(len(result.failed), 2)
            self.assertTrue(all(isinstance(error, MemoryError) for path, error in result.failed))


if __name__ == '__main__':
    unittest.main()
