#!/usr/bin/env python3
"""Merge cover + body into the final Zemest analysis report PDF."""
from pypdf import PdfReader, PdfWriter

A4_W, A4_H = 595.28, 841.89

def normalize(page, force=False):
    box = page.mediabox
    w, h = float(box.width), float(box.height)
    if force or abs(w - A4_W) > 0.1 or abs(h - A4_H) > 0.1:
        page.scale_to(A4_W, A4_H)
        # Force exact mediabox to eliminate sub-point drift
        page.mediabox.lower_left = (0, 0)
        page.mediabox.upper_right = (A4_W, A4_H)
    return page

COVER = '/home/z/my-project/scripts/assets/cover.pdf'
BODY = '/home/z/my-project/scripts/report_body.pdf'
OUT = '/home/z/my-project/download/Zemest_Deep_Code_Analysis_Report.pdf'

writer = PdfWriter()
writer.add_page(normalize(PdfReader(COVER).pages[0], force=True))
for p in PdfReader(BODY).pages:
    writer.add_page(normalize(p))
writer.add_metadata({
    '/Title': 'Zemest Deep Code Analysis Report',
    '/Author': 'Z.ai',
    '/Creator': 'Z.ai',
    '/Subject': 'Full-stack 20-agent audit of zemest (FastAPI) and zemest-platform (Next.js)',
})
with open(OUT, 'wb') as f:
    writer.write(f)
print('Merged final PDF:', OUT)
print('Total pages:', 1 + len(PdfReader(BODY).pages))
