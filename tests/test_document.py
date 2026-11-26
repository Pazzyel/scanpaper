import tempfile
from pathlib import Path
import unittest

from PIL import Image, ImageDraw
from pypdf import PdfReader

from scanpaper.document import Document, export_documents
from scanpaper.model import Layout, PT_PER_MM


class DocumentTests(unittest.TestCase):
    def make_image(self, path, size):
        with Image.new('RGB', size, 'white') as image:
            ImageDraw.Draw(image).rectangle((10, 10, 40, 40), fill='black')
            image.save(path)
        return Document(path)

    def test_one_pdf_follows_supplied_order_and_preserves_each_layout(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            first = self.make_image(folder / '第一张.jpg', (120, 180))
            second = self.make_image(folder / '第二张.JPG', (240, 120))
            third = self.make_image(folder / '第三张.jpeg', (150, 100))
            second.layout = Layout(paper='A3', landscape=True)
            third.layout = Layout(paper='A2', x=23, y=31, width=100, height=150, rotation=1)
            third.fitted = True
            destination = folder / '合并.pdf'
            progress = []
            export_documents([second, third, first], destination, progress.append)

            self.assertEqual(list(folder.glob('*.pdf')), [destination])
            self.assertEqual(progress, [1, 2, 3])
            pages = PdfReader(destination).pages
            self.assertEqual(len(pages), 3)
            for page, document, size in zip(pages, [second, third, first], [(240, 120), (100, 150), (120, 180)]):
                paper_width, paper_height = document.layout.paper_size
                self.assertAlmostEqual(float(page.mediabox.width), paper_width * PT_PER_MM, places=3)
                self.assertAlmostEqual(float(page.mediabox.height), paper_height * PT_PER_MM, places=3)
                resource = next(iter(page['/Resources']['/XObject'].values())).get_object()
                self.assertEqual((resource['/Width'], resource['/Height']), size)
                self.assertIn('/SMask', resource)
            transform = [args for args, op in pages[1].get_contents().operations if op == b'cm'][-1]
            self.assertAlmostEqual(float(transform[0]), 100 * PT_PER_MM, places=3)
            self.assertAlmostEqual(float(transform[4]), 23 * PT_PER_MM, places=3)

    def test_unreadable_page_aborts_export_without_replacing_existing_pdf(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            first = self.make_image(folder / 'first.jpg', (120, 180))
            broken = folder / '损坏.jpg'
            broken.write_bytes(b'broken jpeg')
            destination = folder / 'existing.pdf'
            export_documents([first], destination)
            original = destination.read_bytes()
            with self.assertRaisesRegex(ValueError, '第 2 页（损坏.jpg）'):
                export_documents([first, Document(broken)], destination)
            self.assertEqual(destination.read_bytes(), original)
            self.assertEqual(list(folder.glob('.scanpaper-*')), [])
