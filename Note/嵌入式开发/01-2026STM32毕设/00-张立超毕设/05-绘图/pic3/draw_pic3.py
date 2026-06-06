from html import escape
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
WIDTH_MM = 297
HEIGHT_MM = 210
LINE_W = 0.45
RF_LINE_W = 1.05
FONT_SIZE = 3.2
OUT_FILE = BASE_DIR / "pic3_circuit.svg"


class Svg:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.items = []

    def add(self, item):
        self.items.append(item)

    def line(self, x1, y1, x2, y2, cls=""):
        self.add(f'<line class="{cls}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" />')

    def polyline(self, points, cls=""):
        pts = " ".join(f"{x},{y}" for x, y in points)
        self.add(f'<polyline class="{cls}" points="{pts}" />')

    def path(self, d, cls=""):
        self.add(f'<path class="{cls}" d="{d}" />')

    def rect(self, x, y, w, h, rx=0, cls=""):
        self.add(f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" />')

    def circle(self, x, y, r, fill="none", cls=""):
        self.add(f'<circle class="{cls}" cx="{x}" cy="{y}" r="{r}" fill="{fill}" />')

    def text(self, x, y, value, size=FONT_SIZE, anchor="middle"):
        self.add(
            f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}">'
            f"{escape(value)}</text>"
        )

    def save(self, path):
        style = f"""
  <style>
    svg {{
      background: none;
    }}
    line, polyline, path, rect, circle {{
      stroke: #000;
      stroke-width: {LINE_W};
      fill: none;
      stroke-linecap: round;
      stroke-linejoin: round;
      vector-effect: non-scaling-stroke;
    }}
    .rf {{
      stroke-width: {RF_LINE_W};
    }}
    .dash {{
      stroke-dasharray: 2.4 1.8;
    }}
    text {{
      fill: #000;
      font-family: Arial, 'Microsoft YaHei', sans-serif;
      letter-spacing: 0;
    }}
  </style>"""
        body = "\n  ".join(self.items)
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}mm" '
            f'height="{self.height}mm" viewBox="0 0 {self.width} {self.height}">\n'
            f"{style}\n  {body}\n</svg>\n"
        )
        path.write_text(svg, encoding="utf-8")


def node(s, x, y):
    s.circle(x, y, 0.9, fill="#000")


def rf_wire(s, *points):
    if len(points) == 2:
        s.line(points[0][0], points[0][1], points[1][0], points[1][1], cls="rf")
    else:
        s.polyline(points, cls="rf")


def wire(s, *points):
    if len(points) == 2:
        s.line(points[0][0], points[0][1], points[1][0], points[1][1])
    else:
        s.polyline(points)


def ground(s, x, y, label=False):
    s.line(x, y, x, y + 3)
    s.line(x - 3.2, y + 3, x + 3.2, y + 3)
    s.line(x - 2.1, y + 5, x + 2.1, y + 5)
    s.line(x - 1.0, y + 7, x + 1.0, y + 7)
    if label:
        s.text(x + 8, y + 5, "系统地", anchor="start")


def rf_pin(s, x, y):
    s.rect(x - 10, y - 6, 20, 12)
    s.text(x, y - 9, "核心子板")
    s.text(x, y + 1.1, "RF_OUT")


def inductor_h(s, x1, x2, y, ref, value):
    lead = 5
    start = x1 + lead
    end = x2 - lead
    loops = 4
    span = (end - start) / loops
    rf_wire(s, (x1, y), (start, y))
    d = f"M {start} {y}"
    cur = start
    for _ in range(loops):
        nxt = cur + span
        d += f" A {span / 2} {span / 2} 0 0 1 {nxt} {y}"
        cur = nxt
    s.path(d, cls="rf")
    rf_wire(s, (end, y), (x2, y))
    s.text((x1 + x2) / 2, y - 11, ref)
    s.text((x1 + x2) / 2, y + 10, value)


def capacitor_to_ground(s, x, y_top, y_bus, ref, value):
    plate_a = y_top + 16
    plate_b = y_top + 22
    rf_wire(s, (x, y_top), (x, plate_a))
    s.line(x - 6, plate_a, x + 6, plate_a)
    s.line(x - 6, plate_b, x + 6, plate_b)
    wire(s, (x, plate_b), (x, y_bus))
    s.text(x + 9, y_top + 13, ref, anchor="start")
    s.text(x + 9, y_top + 20, value, anchor="start")


def resistor_h(s, x1, x2, y, ref, value):
    mid = (x1 + x2) / 2
    body_w = 15
    left = mid - body_w / 2
    right = mid + body_w / 2
    rf_wire(s, (x1, y), (left, y))
    s.rect(left, y - 3.2, body_w, 6.4)
    rf_wire(s, (right, y), (x2, y))
    s.text(mid, y - 10.5, ref)
    s.text(mid, y + 11, value)


def power_pad(s, x, y, ref, label):
    s.rect(x - 6, y - 4, 12, 8, rx=1.2)
    s.text(x, y - 8, ref)
    s.text(x, y + 11, label)


def sma_connector(s, x, y, ground_bus_y):
    s.rect(x - 8, y - 12, 16, 24)
    s.text(x, y - 17, "J1")
    s.text(x, y + 18, "SMA天线座")
    rf_wire(s, (x - 8, y), (x + 8, y))
    s.circle(x, y, 2.0)
    wire(s, (x, y + 12), (x, ground_bus_y))


def antenna(s, x, y):
    s.line(x, y, x, y - 18, cls="rf")
    s.line(x, y - 18, x - 9, y - 29, cls="rf")
    s.line(x, y - 18, x + 9, y - 29, cls="rf")
    s.line(x, y - 12, x - 7, y - 20, cls="rf")
    s.line(x, y - 12, x + 7, y - 20, cls="rf")
    s.text(x, y - 35, "ANT1")
    s.text(x, y + 10, "2dBi全向天线")


def draw():
    s = Svg(WIDTH_MM, HEIGHT_MM)

    y = 90
    ground_y = 142

    rf_pin(s, 24, y)
    rf_wire(s, (34, y), (42, y))
    inductor_h(s, 42, 82, y, "L2", "27nH 贴片电感")

    node(s, 92, y)
    rf_wire(s, (82, y), (92, y))
    capacitor_to_ground(s, 92, y, ground_y, "C4", "12pF 贴片电容")

    inductor_h(s, 104, 144, y, "L3", "27nH 贴片电感")
    rf_wire(s, (92, y), (104, y))

    node(s, 154, y)
    rf_wire(s, (144, y), (154, y))
    capacitor_to_ground(s, 154, y, ground_y, "C7", "12pF 贴片电容")

    resistor_h(s, 166, 206, y, "R8", "33Ω 射频隔离电阻")
    rf_wire(s, (154, y), (166, y))

    power_pad(s, 222, y, "P1", "0.5W")
    rf_wire(s, (206, y), (216, y))
    rf_wire(s, (228, y), (240, y))

    power_pad(s, 222, 58, "P2", "2W")
    s.line(222, 62, 222, 86, cls="dash")

    sma_connector(s, 248, y, ground_y)
    rf_wire(s, (240, y), (248, y))
    rf_wire(s, (256, y), (272, y))
    antenna(s, 272, y)

    wire(s, (92, ground_y), (248, ground_y))
    ground(s, 170, ground_y, label=True)

    s.save(OUT_FILE)


if __name__ == "__main__":
    draw()
