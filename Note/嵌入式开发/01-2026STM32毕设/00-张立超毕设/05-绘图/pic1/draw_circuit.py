from html import escape
from pathlib import Path


WIDTH_MM = 297
HEIGHT_MM = 210
LINE_W = 0.45
FONT_SIZE = 3.2
OUT_FILE = Path("circuit_diagram.svg")


class Svg:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.items = []

    def add(self, item):
        self.items.append(item)

    def line(self, x1, y1, x2, y2):
        self.add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" />')

    def polyline(self, points):
        pts = " ".join(f"{x},{y}" for x, y in points)
        self.add(f'<polyline points="{pts}" />')

    def path(self, d):
        self.add(f'<path d="{d}" />')

    def rect(self, x, y, w, h, rx=0):
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" />')

    def circle(self, x, y, r, fill="none"):
        self.add(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" />')

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
    s.circle(x, y, 0.85, fill="#000")


def wire(s, *points):
    if len(points) == 2:
        s.line(points[0][0], points[0][1], points[1][0], points[1][1])
    else:
        s.polyline(points)


def ground(s, x, y):
    s.line(x, y, x, y + 3)
    s.line(x - 3.2, y + 3, x + 3.2, y + 3)
    s.line(x - 2.1, y + 5, x + 2.1, y + 5)
    s.line(x - 1.0, y + 7, x + 1.0, y + 7)


def vcc(s, x, y, label):
    s.line(x, y, x, y + 5)
    s.polyline([(x - 3, y), (x, y - 3), (x + 3, y)])
    s.text(x, y - 5, label)


def pad(s, x, y, label):
    s.circle(x, y, 2.2)
    s.text(x - 7, y + 1.1, label, anchor="end")


def resistor_h(s, x1, x2, y, label, value):
    mid = (x1 + x2) / 2
    body_w = min(13, (x2 - x1) * 0.55)
    left = mid - body_w / 2
    right = mid + body_w / 2
    s.line(x1, y, left, y)
    s.rect(left, y - 2.2, body_w, 4.4)
    s.line(right, y, x2, y)
    s.text(mid, y - 5.2, label)
    s.text(mid, y + 7.0, value)


def resistor_v(s, x, y1, y2, label, value, side="right"):
    mid = (y1 + y2) / 2
    body_h = min(13, (y2 - y1) * 0.55)
    top = mid - body_h / 2
    bottom = mid + body_h / 2
    s.line(x, y1, x, top)
    s.rect(x - 2.2, top, 4.4, body_h)
    s.line(x, bottom, x, y2)
    tx = x + 6 if side == "right" else x - 6
    anchor = "start" if side == "right" else "end"
    s.text(tx, mid - 4.0, label, anchor=anchor)
    s.text(tx, mid + 8.0, value, anchor=anchor)


def capacitor_h(s, x1, x2, y, label, value, plus_at_left=False):
    mid = (x1 + x2) / 2
    gap = 2.8
    s.line(x1, y, mid - gap, y)
    s.line(mid - gap, y - 5, mid - gap, y + 5)
    s.line(mid + gap, y - 5, mid + gap, y + 5)
    s.line(mid + gap, y, x2, y)
    if plus_at_left:
        s.text(mid - 6.4, y - 5.5, "+", size=3.8)
    if label:
        s.text(mid, y - 8.0, label)
    if value:
        s.text(mid, y + 9.5, value)


def capacitor_v(s, x, y1, y2, label, value, plus_at_top=False, side="right"):
    mid = (y1 + y2) / 2
    gap = 2.8
    s.line(x, y1, x, mid - gap)
    s.line(x - 5, mid - gap, x + 5, mid - gap)
    s.line(x - 5, mid + gap, x + 5, mid + gap)
    s.line(x, mid + gap, x, y2)
    if plus_at_top:
        s.text(x - 6.5, mid - 4.6, "+", size=3.8)
    tx = x + 7 if side == "right" else x - 7
    anchor = "start" if side == "right" else "end"
    s.text(tx, mid - 1.5, label, anchor=anchor)
    s.text(tx, mid + 4.0, value, anchor=anchor)


def diode_h(s, x1, x2, y, label, value, schottky=False, led=False):
    mid = (x1 + x2) / 2
    tri_left = mid - 4.5
    bar_x = mid + 4.2
    s.line(x1, y, tri_left, y)
    s.polyline([(tri_left, y - 5), (tri_left, y + 5), (bar_x, y), (tri_left, y - 5)])
    s.line(bar_x, y - 5.5, bar_x, y + 5.5)
    if schottky:
        s.polyline([(bar_x + 2.0, y - 5.5), (bar_x, y - 5.5), (bar_x, y - 3.2)])
        s.polyline([(bar_x - 2.0, y + 5.5), (bar_x, y + 5.5), (bar_x, y + 3.2)])
    if led:
        s.polyline([(mid + 3.5, y - 8.5), (mid + 8.5, y - 12.0), (mid + 7.0, y - 9.0)])
        s.polyline([(mid + 7.0, y - 6.5), (mid + 12.0, y - 10.0), (mid + 10.5, y - 7.0)])
    s.line(bar_x, y, x2, y)
    s.text(mid, y - 9.5, label)
    s.text(mid, y + 9.0, value)


def switch_h(s, x1, x2, y, label, value):
    left = x1 + 5
    right = x2 - 5
    s.line(x1, y, left, y)
    s.circle(left, y, 1.1)
    s.circle(right, y, 1.1)
    s.line(right, y, x2, y)
    s.line(left + 1.5, y - 1.2, right - 2.0, y - 6.0)
    s.text((x1 + x2) / 2, y - 10.0, label)
    s.text((x1 + x2) / 2, y + 8.0, value)


def mic(s, x, y):
    s.circle(x, y, 8.0)
    s.line(x + 8, y - 3, x + 13, y - 3)
    s.line(x, y + 8, x, y + 16)
    s.text(x - 3.6, y - 1.8, "+", size=3.8)
    s.text(x - 3.6, y + 4.5, "-", size=3.8)
    s.text(x - 14.0, y + 1.0, "MIC1", anchor="end")
    s.text(x, y + 24.0, "Electret")


def speaker(s, x, y):
    s.rect(x, y - 5.0, 4.0, 10.0)
    s.polyline([(x + 4, y - 6), (x + 13, y - 12), (x + 13, y + 12), (x + 4, y + 6)])
    s.path(f"M {x + 16} {y - 7} Q {x + 22} {y} {x + 16} {y + 7}")
    s.path(f"M {x + 20} {y - 10} Q {x + 28} {y} {x + 20} {y + 10}")
    s.text(x + 14, y - 16, "SPK1")
    s.text(x + 30, y + 18, "8Ω/0.5W", anchor="start")


def chip_lm4871(s, x, y, w, h):
    s.rect(x, y, w, h)
    s.text(x + w / 2, y + h / 2 - 2.5, "U1")
    s.text(x + w / 2, y + h / 2 + 3.2, "LM4871")

    top_pins = [(1, 108), (4, 150), (5, 130)]
    bottom_pins = [(2, 116), (6, 140)]
    right_pins = [(3, 166), (8, 176)]

    for num, px in top_pins:
        s.line(px, y - 5, px, y)
        s.text(px + 1.2, y + 3.6, str(num), size=2.7, anchor="start")
    for num, px in bottom_pins:
        s.line(px, y + h, px, y + h + 5)
        s.text(px + 1.2, y + h - 2.2, str(num), size=2.7, anchor="start")
    for num, py in right_pins:
        s.line(x + w, py, x + w + 5, py)
        s.text(x + w - 2.5, py + 1.1, str(num), size=2.7, anchor="end")


def core_board(s, x, y, w, h):
    s.rect(x, y, w, h)
    s.text(x + w / 2, y + 8.0, "CORE")
    s.text(x + w / 2, y + 13.0, "SUBBOARD")

    left = [("PTT", 58), ("TXLED", 76), ("RXLED", 100), ("MIC_IN", 118), ("AF_OUT", 126)]
    right = [("PD", 58), ("SQ", 72), ("TXD", 86), ("RXD", 100), ("GND", 114), ("+3V", 128)]

    for name, py in left:
        s.line(x - 5, py, x, py)
        s.text(x + 2.5, py + 1.1, name, size=2.9, anchor="start")
    for name, py in right:
        s.line(x + w, py, x + w + 5, py)
        s.text(x + w - 2.5, py + 1.1, name, size=2.9, anchor="end")


def connector_pin(s, x, y, label):
    s.circle(x, y, 1.4)
    s.text(x + 5, y + 1.1, label, anchor="start")


def draw():
    s = Svg(WIDTH_MM, HEIGHT_MM)

    # Battery input and post-Schottky supply net.
    pad(s, 18, 22, "BAT+")
    pad(s, 18, 40, "BAT-")
    wire(s, (20.2, 22), (32, 22))
    diode_h(s, 32, 60, 22, "D1", "1N5819", schottky=True)
    node(s, 60, 22)
    wire(s, (60, 22), (118, 22))
    wire(s, (60, 22), (60, 152))
    s.text(85, 17, "+VBAT_SW")
    wire(s, (20.2, 40), (28, 40))
    ground(s, 28, 40)

    capacitor_v(s, 82, 22, 49, "C1", "100uF/10V", plus_at_top=True)
    ground(s, 82, 49)
    capacitor_v(s, 102, 22, 49, "C2", "100nF")
    ground(s, 102, 49)

    # PTT control.
    wire(s, (60, 58), (90, 58))
    switch_h(s, 90, 126, 58, "S1", "6x6mm")
    wire(s, (126, 58), (174, 58))
    node(s, 138, 58)
    resistor_v(s, 138, 36, 58, "R2", "1kΩ")
    vcc(s, 138, 33, "+3.3V")

    # TX/RX indicator LEDs.
    wire(s, (60, 76), (76, 76))
    resistor_h(s, 76, 102, 76, "R1", "1kΩ")
    diode_h(s, 108, 132, 76, "LED1", "RED TX", led=True)
    wire(s, (102, 76), (108, 76))
    wire(s, (132, 76), (174, 76))

    wire(s, (60, 100), (76, 100))
    resistor_h(s, 76, 102, 100, "R3", "1kΩ")
    diode_h(s, 108, 132, 100, "LED2", "GREEN RX", led=True)
    wire(s, (102, 100), (108, 100))
    wire(s, (132, 100), (174, 100))

    # Electret microphone input.
    mic(s, 75, 113)
    wire(s, (88, 110), (88, 118), (94, 118))
    capacitor_h(s, 94, 121, 118, "C3", "10nF")
    wire(s, (121, 118), (174, 118))
    ground(s, 75, 129)

    # Audio power amplifier.
    wire(s, (174, 126), (174, 166))
    capacitor_h(s, 160, 174, 166, "", "")
    s.text(181, 158, "C4", anchor="start")
    s.text(181, 164, "100nF", anchor="start")
    node(s, 160, 166)
    wire(s, (154, 166), (160, 166))
    resistor_v(s, 160, 140, 166, "R4", "100kΩ", side="left")
    ground(s, 160, 133)

    chip_lm4871(s, 102, 146, 52, 38)

    wire(s, (108, 146), (108, 132))
    resistor_h(s, 108, 126, 132, "R5", "100kΩ")
    capacitor_h(s, 130, 150, 132, "C5", "100nF")
    wire(s, (126, 132), (130, 132))
    wire(s, (150, 132), (150, 146))

    wire(s, (116, 184), (116, 191))
    ground(s, 116, 191)

    wire(s, (60, 140), (130, 140), (130, 146))
    node(s, 130, 140)
    capacitor_v(s, 70, 140, 166, "C6", "100nF")
    ground(s, 70, 166)

    wire(s, (140, 184), (140, 191))
    ground(s, 140, 191)

    wire(s, (154, 176), (158, 176), (158, 184), (162, 184))
    capacitor_h(s, 162, 190, 184, "C7", "100uF/10V", plus_at_left=True)
    wire(s, (190, 184), (207, 184))
    speaker(s, 207, 184)
    wire(s, (220, 184), (220, 198))
    ground(s, 220, 198)

    # Core subboard and right-side interface.
    core_board(s, 174, 48, 50, 88)
    io_labels = [("PD", 58), ("SQ", 72), ("TXD", 86), ("RXD", 100), ("GND", 114), ("+3V", 128)]
    for label, py in io_labels:
        wire(s, (224, py), (255, py))
        connector_pin(s, 260, py, label)
    s.text(260, 48, "J1", anchor="middle")

    s.save(OUT_FILE)


if __name__ == "__main__":
    draw()
