from dataclasses import dataclass
import warnings

import cv2
import numpy as np
from PIL import Image, ImageOps

MAX_PIXELS = 64_000_000
PREVIEW_EDGE = 1500


@dataclass(frozen=True)
class Cleanup:
    background: int = 35
    ink: int = 45


def load_jpeg(path):
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(path) as opened:
            if opened.format != "JPEG":
                raise ValueError("请选择真正的 JPG / JPEG 扫描图片")
            if opened.width * opened.height > MAX_PIXELS:
                raise ValueError("图片超过 6400 万像素，请先缩小后再导入")
            image = ImageOps.exif_transpose(opened).convert("RGB")
    return image


def thumbnail(image):
    preview = image.copy()
    preview.thumbnail((PREVIEW_EDGE, PREVIEW_EDGE), Image.Resampling.LANCZOS)
    return preview


def clean_image(image, settings=Cleanup()):
    """Estimate paper illumination, then represent black ink with a soft alpha mask.

    Background estimation uses a fixed working scale so export and preview have
    comparable cleanup. Original dark pixels are protected even inside large fills.
    No connected components are removed: punctuation is document content too.
    """
    gray_image = image.convert("L")
    working = gray_image.copy()
    working.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
    gray_small = np.asarray(working)
    kernel_size = max(3, round(max(working.size) * 0.025) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    paper = cv2.morphologyEx(gray_small, cv2.MORPH_CLOSE, kernel)
    paper = cv2.GaussianBlur(paper, (0, 0), max(1, kernel_size / 3))
    background = np.asarray(Image.fromarray(paper).resize(image.size, Image.Resampling.BILINEAR))
    # Work by rows to bound float-array memory for large, full-resolution scans.
    alpha = np.empty((image.height, image.width), dtype=np.uint8)
    gray = np.asarray(gray_image)
    cutoff = 3 + settings.background * 0.30
    gain = 1.0 + settings.ink * 0.018
    for top in range(0, image.height, 256):
        g = gray[top:top + 256].astype(np.float32)
        bg = np.maximum(background[top:top + 256].astype(np.float32), 150)
        darkness = np.maximum(0, 255 - g * 255 / bg)
        coverage = np.clip((darkness - cutoff) / (255 - cutoff), 0, 1)
        coverage = np.power(coverage, 0.70) * gain
        protected = np.clip((155 - g) / 65, 0, 1)
        opacity = np.clip(np.maximum(coverage, protected), 0, 1)
        opacity[g >= 250] = 0
        alpha[top:top + 256] = np.rint(opacity * 255).astype(np.uint8)
    output = Image.new("RGBA", image.size, (0, 0, 0, 0))
    output.putalpha(Image.fromarray(alpha))
    return output


def rotate_image(image, turns):
    return image if turns % 4 == 0 else image.transpose({
        1: Image.Transpose.ROTATE_270,
        2: Image.Transpose.ROTATE_180,
        3: Image.Transpose.ROTATE_90,
    }[turns % 4])

