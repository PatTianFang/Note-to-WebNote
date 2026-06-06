from html import escape
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
WIDTH_MM = 297
HEIGHT_MM = 210
LINE_W = 0.45
FONT_SIZE = 3.1
OUT_FILE = BASE_DIR / "pic2_circuit.svg"


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

    def rect(self, x, y, w, h, rx=0, cls=""):
        self.add(f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" />')

    def circle(self, x, y, r, fill="none"):
        self.add(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" />')

    def text(self, x, y, value, size=FONT_SIZE, anchor="middle"):
        self.add(
            f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}">'
            f"{escape(value)}</text>"
        )

    def arrow(self, points, cls="arrow"):
        pts = " ".join(f"{x},{y}" for x, y in points)
        self.add(f'<polyline class="{cls}" marker-end="url(#arrow)" points="{pts}" />')

    def save(self, path):
        style = f"""
  <defs>
    <marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
      <path d="M0,0 L7,3.5 L0,7" fill="none" stroke="#000" stroke-width="{LINE_W}" />
    </marker>
  </defs>
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
    .dash {{
      stroke-dasharray: 2.5 1.8;
    }}
    .arrow {{
      stroke-width: {LINE_W};
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


def resistor_v(s, x, y1, y2, ref, value, side="right"):
    mid = (y1 + y2) / 2
    body_h = min(13, (y2 - y1) * 0.55)
    top = mid - body_h / 2
    bottom = mid + body_h / 2
    s.line(x, y1, x, top)
    s.rect(x - 2.2, top, 4.4, body_h)
    s.line(x, bottom, x, y2)
    tx = x + 6 if side == "right" else x - 6
    anchor = "start" if side == "right" else "end"
    s.text(tx, mid - 1.8, ref, anchor=anchor)
    s.text(tx, mid + 4.0, value, anchor=anchor)


def capacitor_v(s, x, y1, y2, ref, value, polarized=False, side="right"):
    mid = (y1 + y2) / 2
    gap = 2.8
    s.line(x, y1, x, mid - gap)
    s.line(x - 5, mid - gap, x + 5, mid - gap)
    s.line(x - 5, mid + gap, x + 5, mid + gap)
    s.line(x, mid + gap, x, y2)
    if polarized:
        s.text(x - 6.5, mid - 4.8, "+", size=3.8)
    tx = x + 7 if side == "right" else x - 7
    anchor = "start" if side == "right" else "end"
    s.text(tx, mid - 4.0, ref, anchor=anchor)
    s.text(tx, mid + 8.0, value, anchor=anchor)


def led_h(s, x1, x2, y, ref, value, cathode_left=True):
    mid = (x1 + x2) / 2
    bar_x = mid - 4 if cathode_left else mid + 4
    tri_x = mid + 4 if cathode_left else mid - 4
    s.line(x1, y, bar_x, y)
    s.line(bar_x, y - 5.2, bar_x, y + 5.2)
    if cathode_left:
        s.polyline([(tri_x, y - 5), (tri_x, y + 5), (bar_x, y), (tri_x, y - 5)])
    else:
        s.polyline([(tri_x, y - 5), (tri_x, y + 5), (bar_x, y), (tri_x, y - 5)])
    s.line(tri_x, y, x2, y)
    s.polyline([(mid + 2, y - 8), (mid + 7, y - 12), (mid + 5.5, y - 9)])
    s.polyline([(mid + 6, y - 5), (mid + 11, y - 9), (mid + 9.5, y - 6)])
    s.text(mid, y - 14, ref)
    s.text(mid, y + 9, value)


def battery(s, x, y):
    s.line(x, y - 10, x, y - 4)
    s.line(x - 4, y - 4, x + 4, y - 4)
    s.line(x - 2.4, y, x + 2.4, y)
    s.line(x, y, x, y + 8)
    s.text(x - 10, y - 5, "+", anchor="end")
    s.text(x - 10, y + 3, "-", anchor="end")
    s.text(x, y + 15, "BT1")
    s.text(x, y + 20, "3.7V Li-ion")


def external_block(s, x, y, w, h, ref, label):
    s.rect(x, y, w, h)
    s.text(x + w / 2, y + h / 2 - 1.5, ref)
    s.text(x + w / 2, y + h / 2 + 4.0, label)


def pad(s, x, y, label, side="right"):
    s.circle(x, y, 1.45)
    if side == "right":
        s.text(x + 5, y + 1.1, label, anchor="start")
    else:
        s.text(x - 5, y + 1.1, label, anchor="end")


def module_box(s, x, y, w, h, title, lines=None):
    s.rect(x, y, w, h, cls="dash")
    s.text(x + w / 2, y + 6, title)
    if lines:
        for index, line in enumerate(lines):
            s.text(x + w / 2, y + 13 + index * 6, line, size=2.8)


def core_board(s, x, y, w, h):
    s.rect(x, y, w, h)
    s.text(x + w / 2, y + 12, "U2")
    s.text(x + w / 2, y + 19, "集成化中频射频子板")

    left_pins = [
        ("VBAT", 50),
        ("GND", 62),
        ("PTT", 77),
        ("PD", 91),
        ("MIC_IN", 118),
        ("RF_IN", 145),
    ]
    right_pins = [
        ("TXLED", 50),
        ("RXLED", 78),
        ("RF_OUT", 97),
        ("AF_OUT", 119),
        ("SQ", 137),
        ("TXD", 152),
        ("RXD", 164),
    ]

    for label, py in left_pins:
        s.line(x - 5, py, x, py)
        s.text(x + 2.5, py + 1.1, label, size=2.8, anchor="start")
    for label, py in right_pins:
        s.line(x + w, py, x + w + 5, py)
        s.text(x + w - 2.5, py + 1.1, label, size=2.8, anchor="end")

    module_box(s, 138, 86, 34, 38, "FM调制解调", ["FM调制", "FM解调"])
    module_box(s, 180, 87, 33, 24, "本振/混频")
    module_box(s, 180, 126, 33, 18, "中频放大")
    module_box(s, 138, 135, 36, 18, "静噪控制")

    s.arrow([(125, 118), (138, 100), (180, 100)])
    s.arrow([(213, 97), (225, 97)])
    s.arrow([(125, 145), (180, 145), (196, 126)])
    s.arrow([(196, 111), (172, 113)])
    s.arrow([(138, 113), (125, 119)])
    s.arrow([(156, 124), (156, 135)])
    s.arrow([(174, 144), (174, 137), (225, 137)])


def draw():
    s = Svg(WIDTH_MM, HEIGHT_MM)

    ux, uy, uw, uh = 120, 32, 105, 144

    # Power input, decoupling, and board ground.
    battery(s, 28, 61)
    wire(s, (28, 51), (55, 51), (55, 50), (115, 50))
    node(s, 55, 50)
    capacitor_v(s, 68, 50, 80, "C7", "100nF", side="left")
    ground(s, 68, 80)
    capacitor_v(s, 86, 50, 80, "C8", "10uF", polarized=True, side="right")
    ground(s, 86, 80)
    wire(s, (28, 69), (38, 69))
    ground(s, 38, 69)
    wire(s, (115, 62), (103, 62))
    ground(s, 103, 62)

    # PTT and PD pull-ups.
    wire(s, (115, 77), (105, 77))
    resistor_v(s, 105, 58, 77, "R5", "10kΩ", side="right")
    vcc(s, 105, 52, "+3.3V")
    wire(s, (115, 91), (96, 91))
    resistor_v(s, 96, 72, 91, "R6", "10kΩ", side="right")
    vcc(s, 96, 69, "+3.3V")

    # External microphone and RF input.
    external_block(s, 28, 110, 42, 17, "J_MIC", "外部麦克风输入")
    wire(s, (70, 118), (115, 118))
    external_block(s, 28, 137, 42, 17, "NET1", "高频匹配输入")
    wire(s, (70, 145), (115, 145))

    # LED cathodes, RF output, audio, SQ, and serial interface.
    wire(s, (230, 50), (240, 50))
    led_h(s, 240, 264, 50, "LED1", "RED 阴极", cathode_left=True)
    pad(s, 269, 50, "A")

    wire(s, (230, 78), (240, 78))
    led_h(s, 240, 264, 78, "LED2", "GREEN 阴极", cathode_left=True)
    pad(s, 269, 78, "A")

    external_block(s, 238, 89, 44, 16, "NET2", "高频匹配输出")
    wire(s, (230, 97), (238, 97))

    external_block(s, 238, 111, 44, 16, "U1", "LM4871 IN")
    wire(s, (230, 119), (238, 119))

    external_block(s, 238, 129, 44, 16, "EN1", "功放使能端")
    wire(s, (230, 137), (238, 137))

    wire(s, (230, 152), (265, 152))
    pad(s, 270, 152, "TXD")
    wire(s, (230, 164), (265, 164))
    pad(s, 270, 164, "RXD")
    s.text(270, 176, "J_UART")

    core_board(s, ux, uy, uw, uh)

    s.save(OUT_FILE)


if __name__ == "__main__":
    draw()
