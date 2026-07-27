"""Contact sheet of everything ONE clip produces — the overview talk's "what comes out" slide.

Rebuild after a re-run:  python presentation/figs/mk_talk_artifacts.py
Captions are sized generously relative to the cell: the sheet is scaled to slide width, so a
caption that looks large here lands at about 2 cm on the projector.
"""
import os
import subprocess
import matplotlib
from PIL import Image, ImageDraw, ImageFont

FONTDIR = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
W = ("/home/damar/centri/agent-backend/workspaces/"
     "job_roundabout-4046-final/analysis_output")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "talk-artifacts.png")

# The worksheet thumbnails are rendered on demand from the PDFs.
PDFS = [("student_edition.basic", "basic worksheet"),
        ("student_edition.intermediate", "intermediate"),
        ("student_edition.advanced", "advanced"),
        ("teacher_key.advanced", "teacher's copy  x3")]


def thumb(name):
    out = f"/tmp/talkthumb_{name}"
    subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-r", "55", "-png",
                    f"{W}/report/{name}.pdf", out], capture_output=True)
    return f"{out}-1.png"


items = [(f"{W}/plots/annotated_image.png", "marked-up frame"),
         (os.path.join(os.path.dirname(OUT), "talk-annot-video.jpg"), "annotated video"),
         (f"{W}/plots/omega_t.png", "turn rate over time"),
         (f"{W}/plots/ac_t.png", "inward pull over time"),
         (f"{W}/plots/trajectory.png", "the traced path"),
         (f"{W}/plots/angle_points_basic.png", "turns completed"),
         (f"{W}/plots/annotated_table.png", "measurements table"),
         (f"{W}/plots/annotated_image_basic.png", "beginner's frame")]
items += [(thumb(n), lbl) for n, lbl in PDFS]

CELL_W, CELL_H, PAD, CAP, COLS = 400, 300, 12, 54, 6
rows = (len(items) + COLS - 1) // COLS
sheet = Image.new("RGB", (COLS * (CELL_W + PAD) + PAD, rows * (CELL_H + CAP + PAD) + PAD), "white")
d = ImageDraw.Draw(sheet)
font = ImageFont.truetype(os.path.join(FONTDIR, "DejaVuSans-Bold.ttf"), 34)
for i, (path, label) in enumerate(items):
    c, r = i % COLS, i // COLS
    x0 = PAD + c * (CELL_W + PAD)
    y0 = PAD + r * (CELL_H + CAP + PAD)
    try:
        im = Image.open(path).convert("RGB")
    except OSError:
        print(f"MISSING {path}")
        continue
    im.thumbnail((CELL_W, CELL_H), Image.LANCZOS)
    d.rectangle([x0 - 1, y0 - 1, x0 + CELL_W, y0 + CELL_H], outline="#CCCCCC")
    sheet.paste(im, (x0 + (CELL_W - im.width) // 2, y0 + (CELL_H - im.height) // 2))
    w = d.textlength(label, font=font)
    d.text((x0 + (CELL_W - w) / 2, y0 + CELL_H + 9), label, fill="#333333", font=font)
sheet.save(OUT)
print("wrote", OUT, sheet.size)
