"""Make hand-written fake "scans" with known text for the OCR bake-off (no real coursework).

Writes samples/<name>.pdf or .png and samples/<name>.txt (the ground truth).
"""
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).parent / "samples"
OUT.mkdir(exist_ok=True)
FONTS = Path("C:/Windows/Fonts")
DPI = 200
W, H = int(8.5 * DPI), int(11 * DPI)

HANDOUT = [
    "CptS 101 Midterm Review Handout",
    "Exam 1 is on October 12 in Sloan 175 at 9:10 am.",
    "Bring a pencil and your student ID card.",
    "Topics: recursion, linked lists, Big-O notation,",
    "binary search trees, and hash tables.",
    "Practice problem 4: write a function that reverses",
    "a singly linked list in place without extra memory.",
    "Office hours move to Thursday 2-4 pm this week only.",
]
SLIDE = [
    "Lecture 7: Sorting Algorithms",
    "Merge sort runs in O(n log n) time",
    "Quicksort is fast on average",
    "Insertion sort is good for small arrays",
    "Homework 3 due Friday at midnight",
]


def page(lines, font, size, spacing, bg=255, fg=0, top=150, left=150):
    img = Image.new("L", (W, H), bg)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(str(FONTS / font), size)
    y = top
    for line in lines:
        d.text((left, y), line, font=f, fill=fg)
        y += int(size * spacing)
    return img


def photocopy(img, seed=1):
    """Make a clean page look like a cheap scan: tilt, blur, grey paper, speckle noise."""
    rnd = random.Random(seed)
    img = img.rotate(1.5, resample=Image.BICUBIC, expand=False, fillcolor=255)
    img = img.filter(ImageFilter.GaussianBlur(1.0))
    px = img.load()
    for _ in range(W * H // 60):
        x, y = rnd.randrange(W), rnd.randrange(H)
        px[x, y] = rnd.choice([0, 90, 160])
    # grey paper, weaker ink
    return img.point(lambda v: int(60 + v * 0.65))


def save_pdf(name, pages, truth):
    pages[0].convert("RGB").save(OUT / f"{name}.pdf", save_all=True,
                                 append_images=[p.convert("RGB") for p in pages[1:]], resolution=DPI)
    (OUT / f"{name}.txt").write_text("\n".join(truth), encoding="utf-8")


def main():
    # 1. clean printed handout, 12 pt Times
    clean = page(HANDOUT, "times.ttf", 34, 1.6)
    save_pdf("1_clean_handout", [clean], HANDOUT)
    # 2. the same handout as a bad photocopy
    save_pdf("2_photocopy_handout", [photocopy(clean)], HANDOUT)
    # 3. a slide: big text, white on dark blue, landscape
    slide = Image.new("RGB", (int(13.33 * 100), int(7.5 * 100)), (20, 40, 110))
    d = ImageDraw.Draw(slide)
    d.text((60, 50), SLIDE[0], font=ImageFont.truetype(str(FONTS / "arialbd.ttf"), 54), fill="white")
    for i, line in enumerate(SLIDE[1:]):
        d.text((90, 190 + i * 90), "- " + line, font=ImageFont.truetype(str(FONTS / "arial.ttf"), 40),
               fill=(230, 230, 230))
    slide.save(OUT / "3_slide.pdf", resolution=100)
    (OUT / "3_slide.txt").write_text("\n".join(SLIDE), encoding="utf-8")
    # 4. small 9 pt text, two pages, every sentence different (speed and small-print accuracy)
    rnd = random.Random(7)
    vocab = ("late work loses ten percent per day unless you email the instructor before the deadline "
             "quizzes open on monday and close sunday night labs meet in the basement of dana hall "
             "grades are posted within one week of each exam regrade requests need a written reason").split()
    small = [f"{i}. " + " ".join(rnd.choice(vocab) for _ in range(10)) + "." for i in range(1, 41)]
    save_pdf("4_small_print_2pages",
             [page(small[:20], "arial.ttf", 25, 1.5), page(small[20:], "arial.ttf", 25, 1.5)], small)
    # 7. a two-column handout (left column fully, then right column, is the right reading order)
    left = ["Week 1: Introduction", "Read chapter one", "Install the compiler", "Quiz on Friday",
            "Week 2: Variables", "Read chapter two", "Lab 1 due Tuesday"]
    right = ["Week 3: Loops", "Read chapter three", "Lab 2 due Tuesday", "Week 4: Functions",
             "Read chapter four", "Project proposal due", "Midterm next week"]
    two = page(left, "times.ttf", 34, 1.6)
    two.paste(page(right, "times.ttf", 34, 1.6).crop((0, 0, W // 2, H)), (W // 2 + 40, 0))
    save_pdf("7_two_columns", [two], left + right)
    # 5. a photo of text (png): tilted, low contrast
    photo = photocopy(page(HANDOUT[:4], "arial.ttf", 40, 1.7), seed=2).crop((0, 0, W, 800))
    photo.save(OUT / "5_photo_of_text.png")
    (OUT / "5_photo_of_text.txt").write_text("\n".join(HANDOUT[:4]), encoding="utf-8")
    # 6. a diagram with no words: OCR should return (almost) nothing
    diag = Image.new("RGB", (1200, 800), "white")
    d = ImageDraw.Draw(diag)
    for i in range(6):
        d.rectangle((80 + i * 180, 300, 200 + i * 180, 420), outline="black", width=5)
        if i < 5:
            d.line((200 + i * 180, 360, 260 + i * 180, 360), fill="black", width=5)
    d.ellipse((450, 520, 750, 760), outline=(200, 0, 0), width=6)
    diag.save(OUT / "6_diagram_no_text.png")
    (OUT / "6_diagram_no_text.txt").write_text("", encoding="utf-8")
    print(json.dumps(sorted(p.name for p in OUT.iterdir())))


if __name__ == "__main__":
    main()
