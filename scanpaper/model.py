from dataclasses import dataclass
import math

PAPERS = {"A1": (594.0, 841.0), "A2": (420.0, 594.0),
          "A3": (297.0, 420.0), "A4": (210.0, 297.0)}
PT_PER_MM = 72 / 25.4


@dataclass
class Layout:
    paper: str = "A4"
    landscape: bool = False
    x: float = 10.0
    y: float = 10.0
    width: float = 190.0
    height: float = 277.0
    rotation: int = 0

    @property
    def paper_size(self):
        w, h = PAPERS[self.paper]
        return (h, w) if self.landscape else (w, h)

    def fit(self, aspect):
        pw, ph = self.paper_size
        self.width = min(pw - 20, (ph - 20) * aspect)
        self.height = self.width / aspect
        self.center()

    def center(self):
        pw, ph = self.paper_size
        self.x, self.y = (pw - self.width) / 2, (ph - self.height) / 2

    @property
    def overflowing(self):
        pw, ph = self.paper_size
        return (self.x < -0.01 or self.y < -0.01 or
                self.x + self.width > pw + 0.01 or self.y + self.height > ph + 0.01)

    def validate(self):
        if self.paper not in PAPERS:
            raise ValueError("不支持的纸张类型")
        if not all(math.isfinite(v) for v in (self.x, self.y, self.width, self.height)):
            raise ValueError("尺寸和位置必须是有效数字")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("图片尺寸必须大于零")

