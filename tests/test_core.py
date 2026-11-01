import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw
from pypdf import PdfReader

from scanpaper.model import Layout, PAPERS, PT_PER_MM
from scanpaper.processing import Cleanup, clean_image, load_jpeg, rotate_image, thumbnail
from scanpaper.pdf import export_pdf


class ProcessingTests(unittest.TestCase):
    def test_blank_and_near_white_are_transparent(self):
        for tone in (255, 252, 248, 230):
            alpha = np.asarray(clean_image(Image.new('RGB', (120, 160), (tone,) * 3)))[:, :, 3]
            self.assertEqual(int(alpha.max()), 0)

    def test_black_block_punctuation_and_soft_gray_ink(self):
        image = Image.new('RGB', (600, 800), (240, 240, 240))
        draw = ImageDraw.Draw(image)
        draw.rectangle((20, 20, 350, 350), fill='black')
        draw.rectangle((390, 400, 392, 402), fill='black')
        draw.line((20, 600, 500, 600), fill=(195, 195, 195), width=2)
        cleaned = np.asarray(clean_image(image))
        self.assertEqual(cleaned[150, 150, 3], 255)
        self.assertEqual(cleaned[401, 391, 3], 255)
        self.assertEqual(cleaned[780, 550, 3], 0)
        self.assertGreater(cleaned[600, 100, 3], 0)
        self.assertLess(cleaned[600, 100, 3], 255)
        self.assertTrue(np.all(cleaned[:, :, :3] == 0))

    def test_yellow_and_gradient_background(self):
        gray = np.tile(np.linspace(200, 247, 500).astype('uint8'), (700, 1))
        rgb = np.stack((gray, gray, np.maximum(gray.astype(int) - 20, 0).astype('uint8')), axis=2)
        cleaned = np.asarray(clean_image(Image.fromarray(rgb)))[:, :, 3]
        self.assertEqual(int(np.percentile(cleaned, 99)), 0)

    def test_controls_retain_or_remove_faint_strokes(self):
        image = Image.new('RGB', (400, 500), (245, 245, 245))
        ImageDraw.Draw(image).line((10, 250, 390, 250), fill=(220, 220, 220), width=2)
        gentle = np.asarray(clean_image(image, Cleanup(0, 45)))[250, 200, 3]
        strong = np.asarray(clean_image(image, Cleanup(100, 45)))[250, 200, 3]
        darker = np.asarray(clean_image(image, Cleanup(0, 100)))[250, 200, 3]
        self.assertGreater(gentle, strong)
        self.assertGreater(darker, gentle)

    def test_exif_direction_and_invalid_input(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '方向.jpg'
            exif = Image.Exif()
            exif[274] = 6
            Image.new('RGB', (60, 100), 'white').save(path, exif=exif)
            self.assertEqual(load_jpeg(path).size, (100, 60))
            path.write_bytes(b'broken jpeg')
            with self.assertRaises(OSError):
                load_jpeg(path)
            Image.new('RGB', (20, 20)).save(path, format='PNG')
            with self.assertRaises(ValueError):
                load_jpeg(path)

    def test_rotation_thumbnail_and_pixel_limit(self):
        image = Image.new('RGB', (1800, 2400), 'white')
        self.assertEqual(rotate_image(image, 1).size, (2400, 1800))
        self.assertEqual(thumbnail(image).size, (1125, 1500))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'large.jpg'
            image.save(path)
            with patch('scanpaper.processing.MAX_PIXELS', 100):
                with self.assertRaisesRegex(ValueError, '像素'):
                    load_jpeg(path)


class PDFTests(unittest.TestCase):
    def test_every_paper_orientation_mask_and_original_resolution(self):
        image = Image.new('RGBA', (1234, 1789), (0, 0, 0, 127))
        with tempfile.TemporaryDirectory() as folder:
            for name in PAPERS:
                for landscape in (False, True):
                    layout = Layout(paper=name, landscape=landscape, x=17, y=23, width=100, height=145)
                    path = Path(folder) / f'{name}-{landscape}.pdf'
                    export_pdf(image, layout, path)
                    pdf = PdfReader(path)
                    self.assertEqual(len(pdf.pages), 1)
                    page = pdf.pages[0]
                    pw, ph = layout.paper_size
                    self.assertAlmostEqual(float(page.mediabox.width), pw * PT_PER_MM, places=3)
                    self.assertAlmostEqual(float(page.mediabox.height), ph * PT_PER_MM, places=3)
                    resource = next(iter(page['/Resources']['/XObject'].values())).get_object()
                    self.assertEqual((resource['/Width'], resource['/Height']), image.size)
                    self.assertIn('/SMask', resource)
                    content = page.get_contents().get_data().decode('latin1')
                    self.assertIn(' W', content)
                    transforms = [args for args, op in page.get_contents().operations if op == b'cm']
                    a, b, c, d, x, y = map(float, transforms[-1])
                    self.assertAlmostEqual(x, 17 * PT_PER_MM, places=3)
                    self.assertAlmostEqual(y, (ph - 23 - 145) * PT_PER_MM, places=3)
                    self.assertAlmostEqual(a, 100 * PT_PER_MM, places=3)
                    self.assertAlmostEqual(d, 145 * PT_PER_MM, places=3)
                    self.assertEqual(resource['/SMask'].get_object().get_data()[0], 127)

    def test_atomic_failure_preserves_existing_pdf(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '已存在.pdf'
            path.write_bytes(b'keep this original')
            with patch('scanpaper.pdf.Canvas.save', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    export_pdf(Image.new('RGBA', (20, 20)), Layout(), path)
            self.assertEqual(path.read_bytes(), b'keep this original')
            self.assertEqual(list(Path(folder).glob('.scanpaper-*')), [])

    def test_replace_denied_and_invalid_layout(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'locked.pdf'
            path.write_bytes(b'original')
            with patch('scanpaper.pdf.os.replace', side_effect=PermissionError('locked')):
                with self.assertRaises(PermissionError):
                    export_pdf(Image.new('RGBA', (20, 20)), Layout(), path)
            self.assertEqual(path.read_bytes(), b'original')
            self.assertEqual(list(Path(folder).glob('.scanpaper-*')), [])
            with self.assertRaises(ValueError):
                export_pdf(Image.new('RGBA', (20, 20)), Layout(width=0), path)

    def test_layout_fit_position_and_overflow(self):
        layout = Layout()
        layout.fit(0.75)
        self.assertAlmostEqual(layout.width / layout.height, 0.75)
        self.assertGreaterEqual(layout.x, 10)
        self.assertGreaterEqual(layout.y, 10)
        self.assertFalse(layout.overflowing)
        layout.x = -1
        self.assertTrue(layout.overflowing)


if __name__ == '__main__':
    unittest.main()
