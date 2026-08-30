#!/usr/bin/env python3
"""Zemest Deep Code Analysis Report — comprehensive PDF generator (ReportLab).

Sources: 20 subagent analyses in /home/z/my-project/analysis/ (856 KB of findings).
Language: English. Fonts: FreeSerif family (registered per skill config).
"""
import os, sys, hashlib

sys.path.insert(0, '/home/z/my-project/skills/pdf/scripts')

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, PageBreak,
                                Table, TableStyle, Image, KeepTogether,
                                CondPageBreak, Flowable, HRFlowable)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from PIL import Image as PILImage

# ─────────────────────────── Fonts ───────────────────────────
FONT_DIR = '/usr/share/fonts'
pdfmetrics.registerFont(TTFont('NotoSerifSC', f'{FONT_DIR}/truetype/noto-serif-sc/NotoSerifSC-Regular.ttf'))
pdfmetrics.registerFont(TTFont('NotoSerifSC-Bold', f'{FONT_DIR}/truetype/noto-serif-sc/NotoSerifSC-Bold.ttf'))
pdfmetrics.registerFont(TTFont('FreeSerif', f'{FONT_DIR}/truetype/freefont/FreeSerif.ttf'))
pdfmetrics.registerFont(TTFont('FreeSerif-Bold', f'{FONT_DIR}/truetype/freefont/FreeSerifBold.ttf'))
pdfmetrics.registerFont(TTFont('FreeSerif-Italic', f'{FONT_DIR}/truetype/freefont/FreeSerifItalic.ttf'))
pdfmetrics.registerFont(TTFont('FreeSerif-BoldItalic', f'{FONT_DIR}/truetype/freefont/FreeSerifBoldItalic.ttf'))
pdfmetrics.registerFont(TTFont('DejaVuSans', f'{FONT_DIR}/truetype/dejavu/DejaVuSansMono.ttf'))
registerFontFamily('NotoSerifSC', normal='NotoSerifSC', bold='NotoSerifSC-Bold')
registerFontFamily('FreeSerif', normal='FreeSerif', bold='FreeSerif-Bold',
                   italic='FreeSerif-Italic', boldItalic='FreeSerif-BoldItalic')
registerFontFamily('DejaVuSans', normal='DejaVuSans', bold='DejaVuSans')

from pdf import install_font_fallback
install_font_fallback()

# ──────────────────── Palette (palette.cascade, seed 42) ────────────────────
PAGE_BG       = colors.HexColor('#f4f5f5')
SECTION_BG    = colors.HexColor('#f0f1f2')
CARD_BG       = colors.HexColor('#e8eaeb')
TABLE_STRIPE  = colors.HexColor('#ebeded')
HEADER_FILL   = colors.HexColor('#32454e')
COVER_BLOCK   = colors.HexColor('#566a74')
BORDER        = colors.HexColor('#acbdc5')
ICON          = colors.HexColor('#4b86a4')
ACCENT        = colors.HexColor('#1f6c92')
ACCENT_2      = colors.HexColor('#c23a50')
TEXT_PRIMARY  = colors.HexColor('#131515')
TEXT_MUTED    = colors.HexColor('#747b7e')
SEM_SUCCESS   = colors.HexColor('#529067')
SEM_WARNING   = colors.HexColor('#8c7443')
SEM_ERROR     = colors.HexColor('#a25b54')

TABLE_HEADER_COLOR = HEADER_FILL
TABLE_ROW_EVEN     = colors.white
TABLE_ROW_ODD      = TABLE_STRIPE

# ─────────────────────────── Geometry ───────────────────────────
MARGIN = 0.9 * inch
PAGE_W, PAGE_H = A4
AVAIL_W = PAGE_W - 2 * MARGIN
AVAIL_H = PAGE_H - 2 * MARGIN
ASSETS = '/home/z/my-project/scripts/assets'
OUT_BODY = '/home/z/my-project/scripts/report_body.pdf'

# ─────────────────────────── Styles ───────────────────────────
S = {}
S['h1'] = ParagraphStyle('H1', fontName='FreeSerif', fontSize=19, leading=24,
                         textColor=TEXT_PRIMARY, spaceBefore=18, spaceAfter=4)
S['h2'] = ParagraphStyle('H2', fontName='FreeSerif', fontSize=14, leading=19,
                         textColor=HEADER_FILL, spaceBefore=14, spaceAfter=6)
S['h3'] = ParagraphStyle('H3', fontName='FreeSerif', fontSize=11.5, leading=16,
                         textColor=TEXT_PRIMARY, spaceBefore=10, spaceAfter=4)
S['body'] = ParagraphStyle('Body', fontName='FreeSerif', fontSize=10.5, leading=17,
                           textColor=TEXT_PRIMARY, alignment=TA_JUSTIFY, spaceAfter=8)
S['bullet'] = ParagraphStyle('Bullet', fontName='FreeSerif', fontSize=10.5, leading=16,
                             textColor=TEXT_PRIMARY, alignment=TA_LEFT,
                             leftIndent=16, bulletIndent=4, spaceAfter=4)
S['caption'] = ParagraphStyle('Caption', fontName='FreeSerif-Italic', fontSize=8.5,
                              leading=12, textColor=TEXT_MUTED, alignment=TA_CENTER,
                              spaceBefore=3, spaceAfter=6)
S['th'] = ParagraphStyle('TH', fontName='FreeSerif', fontSize=9.5, leading=12.5,
                         textColor=colors.white, alignment=TA_LEFT)
S['td'] = ParagraphStyle('TD', fontName='FreeSerif', fontSize=9, leading=12.5,
                         textColor=TEXT_PRIMARY, alignment=TA_LEFT)
S['tdc'] = ParagraphStyle('TDC', fontName='FreeSerif', fontSize=9, leading=12.5,
                          textColor=TEXT_PRIMARY, alignment=TA_CENTER)
S['stat'] = ParagraphStyle('Stat', fontName='FreeSerif', fontSize=19, leading=23,
                           textColor=ACCENT, alignment=TA_CENTER)
S['statlbl'] = ParagraphStyle('StatL', fontName='FreeSerif', fontSize=8.5, leading=11.5,
                              textColor=TEXT_MUTED, alignment=TA_CENTER)
S['quote'] = ParagraphStyle('Quote', fontName='FreeSerif-Italic', fontSize=10.5,
                            leading=16.5, textColor=TEXT_PRIMARY, leftIndent=24,
                            borderPadding=6, spaceBefore=6, spaceAfter=10)
S['toc_title'] = ParagraphStyle('TocTitle', fontName='FreeSerif', fontSize=20, leading=26,
                                textColor=TEXT_PRIMARY, spaceAfter=14)

# ────────────────────── Doc template + TOC ──────────────────────
BODY_START = [2]  # page number where body content begins (TOC = page 1)

class BodyStartMarker(Flowable):
    def __init__(self):
        super().__init__()
        self.width = 0
        self.height = 0
    def wrap(self, aw, ah):
        return (0, 0)
    def draw(self):
        BODY_START[0] = self.canv.getPageNumber()

ROMAN = {1: 'i', 2: 'ii', 3: 'iii', 4: 'iv', 5: 'v', 6: 'vi'}

def footer(canvas, doc):
    page = canvas.getPageNumber()
    if page < BODY_START[0]:
        label = ROMAN.get(page, str(page))
    else:
        label = str(page - BODY_START[0] + 1)
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 0.62 * inch, PAGE_W - MARGIN, 0.62 * inch)
    canvas.setFont('FreeSerif', 7.5)
    canvas.setFillColor(TEXT_MUTED)
    canvas.drawString(MARGIN, 0.45 * inch, 'Zemest Deep Code Analysis')
    canvas.drawRightString(PAGE_W - MARGIN, 0.45 * inch, label)
    canvas.setFont('FreeSerif-Italic', 7.5)
    canvas.drawCentredString(PAGE_W / 2, 0.45 * inch, '20-agent full-stack audit')
    canvas.restoreState()

class TocDocTemplate(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if hasattr(flowable, 'bookmark_name'):
            level = getattr(flowable, 'bookmark_level', 0)
            text = getattr(flowable, 'bookmark_text', '')
            key = getattr(flowable, 'bookmark_key', '')
            self.notify('TOCEntry', (level, text, self.page, key))

# ─────────────────────────── Helpers ───────────────────────────
H1_THRESHOLD = AVAIL_H * 0.25

def heading(text, level=0, num=None):
    """Add a TOC-registered heading. level 0 = H1, 1 = H2."""
    style = S['h1'] if level == 0 else S['h2']
    label = f'{num}  {text}' if num else text
    key = 'h_' + hashlib.md5(f'{num}{text}'.encode()).hexdigest()[:8]
    p = Paragraph(f'<a name="{key}"/><b>{label}</b>', style)
    p.bookmark_name = key
    p.bookmark_level = level
    p.bookmark_text = f'{num}  {text}' if num else text
    p.bookmark_key = key
    return p

def h1_block(num, title, first_flowable=None):
    """H1 + accent rule (+ optionally keep first flowable attached)."""
    items = [heading(title, 0, num),
             HRFlowable(width='100%', thickness=1.2, color=ACCENT,
                        spaceBefore=0, spaceAfter=10)]
    out = [CondPageBreak(H1_THRESHOLD)]
    if first_flowable is not None:
        out.append(KeepTogether(items + [first_flowable]))
    else:
        out.append(KeepTogether(items))
    return out

def h2_block(num, title, first_flowable=None):
    items = [heading(title, 1, num)]
    if first_flowable is not None:
        return [KeepTogether(items + [first_flowable])]
    return [KeepTogether(items)]

def body(text):
    return Paragraph(text, S['body'])

def bullet(text):
    return Paragraph(f'<bullet>•</bullet>{text}', S['bullet'])

def make_table(header, rows, ratios, caption=None, align_center_cols=None):
    """Standard striped table. All cells wrapped in Paragraph."""
    widths = [r * AVAIL_W for r in ratios]
    data = [[Paragraph(f'<b>{h}</b>', S['th']) for h in header]]
    for row in rows:
        cells = []
        for i, c in enumerate(row):
            st = S['tdc'] if (align_center_cols and i in align_center_cols) else S['td']
            cells.append(Paragraph(str(c), st))
        data.append(cells)
    t = Table(data, colWidths=widths, hAlign='CENTER', repeatRows=1)
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), TABLE_HEADER_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4.5),
        ('GRID', (0, 0), (-1, -1), 0.4, BORDER),
    ]
    for i in range(1, len(data)):
        style.append(('BACKGROUND', (0, i), (-1, i),
                      TABLE_ROW_ODD if i % 2 == 0 else TABLE_ROW_EVEN))
    t.setStyle(TableStyle(style))
    out = [Spacer(1, 10), t]
    if caption:
        out += [Paragraph(caption, S['caption']), Spacer(1, 8)]
    else:
        out += [Spacer(1, 10)]
    return out

def stat_row(stats):
    """Row of metric callout boxes. stats = [(value, label), ...]"""
    n = len(stats)
    gap = 8
    box_w = (AVAIL_W - gap * (n - 1)) / n
    cells, widths = [], []
    for i, (v, l) in enumerate(stats):
        inner = Table([[Paragraph(f'<b>{v}</b>', S['stat'])],
                       [Paragraph(l, S['statlbl'])]], colWidths=[box_w - 2])
        inner.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), SECTION_BG),
            ('BOX', (0, 0), (-1, -1), 0.8, BORDER),
            ('LINEABOVE', (0, 0), (-1, 0), 2, ACCENT),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, 1), 2),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        cells.append(inner)
        widths.append(box_w)
        if i < n - 1:
            cells.append('')
            widths.append(gap)
    wrap = Table([cells], colWidths=widths, hAlign='CENTER')
    wrap.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return [Spacer(1, 6), wrap, Spacer(1, 12)]

def chart(png, caption, max_h=300):
    path = os.path.join(ASSETS, png)
    pil = PILImage.open(path)
    ow, oh = pil.size
    ratio = min(AVAIL_W / ow, max_h / oh, 1.0)
    img = Image(path, width=ow * ratio, height=oh * ratio)
    img.hAlign = 'CENTER'
    return [Spacer(1, 20), img, Spacer(1, 4),
            Paragraph(caption, S['caption']), Spacer(1, 16)]

def callout(text, color=ACCENT):
    inner = Table([[Paragraph(text, S['body'])]], colWidths=[AVAIL_W - 8])
    inner.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), SECTION_BG),
        ('LINEBEFORE', (0, 0), (0, -1), 3, color),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    return [Spacer(1, 6), inner, Spacer(1, 10)]

def code_note(text):
    return Paragraph(f'<font name="DejaVuSans" size="8.5" color="#32454e">{text}</font>',
                     ParagraphStyle('CodeNote', parent=S['body'], alignment=TA_LEFT,
                                    backColor=SECTION_BG, borderPadding=7,
                                    leftIndent=8, rightIndent=8, spaceAfter=10))

story = []

# ══════════════════════════ TOC PAGE ══════════════════════════
story.append(Paragraph('<b>Table of Contents</b>', S['toc_title']))
story.append(HRFlowable(width='100%', thickness=1.2, color=ACCENT, spaceAfter=14))
toc = TableOfContents()
toc.levelStyles = [
    ParagraphStyle('TOC1', fontName='FreeSerif', fontSize=10.5, leading=17,
                   leftIndent=14, firstLineIndent=-14, spaceBefore=4, textColor=TEXT_PRIMARY),
    ParagraphStyle('TOC2', fontName='FreeSerif', fontSize=9.5, leading=14.5,
                   leftIndent=30, firstLineIndent=-14, spaceBefore=1, textColor=TEXT_MUTED),
]
toc.dotsMinLevel = 0
story.append(toc)
story.append(PageBreak())
story.append(BodyStartMarker())

# ═════════════════════ 1. EXECUTIVE SUMMARY ═════════════════════
story += h1_block('1', 'Executive Summary')
story.append(body(
    'This report presents the results of a full-depth code audit of the two repositories that '
    'constitute the Zemest product: <b>zemest</b>, a Python/FastAPI backend implementing AI '
    'moderation agents for Facebook Messenger, Instagram Direct, and WhatsApp Business, and '
    '<b>zemest-platform</b>, a Next.js 16 frontend and Backend-for-Frontend (BFF) that presents '
    'the marketing site, tenant dashboard, and admin console. The analysis was executed by twenty '
    'parallel subagents, each assigned a bounded slice of the codebase and instructed to read '
    'every file, trace every function, and catalog every API endpoint in its scope. Their '
    'combined output - 856 KB of structured findings covering 188 backend files (23,116 lines of '
    'Python) and 429 frontend files (15,597 lines of TypeScript) - was then cross-verified and '
    'synthesized into this document.'))
story.append(body(
    'The single most consequential finding is that <b>the two repositories do not actually '
    'integrate</b>. The platform contains a complete and largely correct contract layer - three '
    'BFF authentication routes that forward credentials to the backend and issue httpOnly '
    'cookies, plus a typed API client covering twenty backend endpoints - but none of it is '
    'wired to the user interface. The login form is a <font name="DejaVuSans" size="9">preventDefault()</font> '
    'stub, the API client has zero importers, and all eighteen dashboard and admin pages render '
    'hardcoded mock arrays with no network calls at all. The result is two parallel products '
    'orbiting each other: a functional backend prototype that serves its own second, unauthenticated '
    'Jinja dashboard, and a visually excellent frontend mockup whose forms, buttons, and data are '
    'simulated.'))
story += stat_row([
    ('D+', 'Combined system grade'),
    ('5.5/10', 'Backend quality'),
    ('3/10', 'Frontend functionality'),
    ('8-9/10', 'Frontend design system'),
    ('6-10 wks', 'Gap to closed beta'),
])
story.append(body(
    'The second defining pattern is <b>security machinery that is built but never connected</b>. '
    'A redirect-hardened SSRF-safe HTTP client, a twenty-five-pattern prompt-injection detector, a '
    'Redis-backed rate limiter, an IP-ban system, and a full JWT refresh-and-revocation stack all '
    'exist in the codebase - and all have zero production importers. Grep-verified dead code '
    'certified by dozens of passing tests. Meanwhile the live paths carry ten critical '
    'vulnerabilities, including a crawl endpoint that accepts <font name="DejaVuSans" size="9">file://</font> '
    'URLs, a process-wide Postiz session shared across all tenants, and stored XSS in the backend '
    'dashboard templates.'))
story.append(body(
    'Third, the audit traced the codebase lineage: the backend is a Bangladeshi social-commerce '
    'bot rebranded to Egypt through a destructive migration (the initial schema ships '
    '<font name="DejaVuSans" size="9">name_bn</font> product columns and division/district/upazila '
    'geography), and the frontend is a clone of tavus.io carrying five full pages of Tavus content, '
    'verbatim CSS token names, and fabricated enterprise logos. This provenance matters '
    'practically - the channel the marketing leads with (WhatsApp) is precisely the one the '
    'inherited codebase never had - and it matters for due diligence.'))
story += callout(
    '<b>Verdict.</b> This is a demo, not an MVP. Nothing a customer could sign up for, connect a '
    'channel to, and receive value from exists across both repositories. The encouraging news: '
    'the gap is wiring, not architecture. Tenant isolation is exemplary (zero IDOR findings in 79 '
    'endpoints), the Meta webhook verification is textbook, the order state machine is real, and '
    'the BFF contract layer is well-shaped. A focused six to ten weeks of P0 and P1 remediation '
    'could plausibly lift the Messenger-only flow to a credible closed beta.', ACCENT)

# ═════════════════════ 2. SCOPE & METHODOLOGY ═════════════════════
story += h1_block('2', 'Scope and Methodology')
story.append(body(
    'The audit was organized as a twenty-agent analysis matrix: twelve agents (Z1-Z12) covered the '
    'FastAPI backend in layered slices - bootstrap and deployment, the AI core in two parts, both '
    'halves of the API layer, data models and schemas, both service layers, the knowledge/RAG '
    'engine, the middleware and security utilities, the scheduling and admin subsystems, and the '
    'test suite and documentation. Six agents (P1-P6) covered the Next.js platform in equivalent '
    'slices: the app shell and design system, all twenty-six marketing pages, the tenant dashboard, '
    'the admin and authentication pages, the BFF routes and data layer, and the component library. '
    'Two capstone agents (X1, X2) performed the cross-repository security audit and the integration '
    'synthesis, respectively, building on and independently re-verifying the findings of the other '
    'eighteen.'))
story.append(body(
    'Methodological rigor was enforced throughout. Every claim in this report carries a file and '
    'line reference back to the source. Where feasible, agents verified behavior dynamically: the '
    'test suite was actually installed and executed (yielding a measured 418 passed / 10 failed / '
    '14 skipped / 8 errors), the orders-create endpoint was reproduced outside pytest to confirm a '
    'guaranteed 500, dead code was proven via importer greps rather than assumed, and one agent ran '
    'executable simulations of the retrieval engine to confirm double-counting bugs. Findings were '
    'then cross-checked between agents - for example, three agents independently converged on the '
    'missing <font name="DejaVuSans" size="9">lib/pageindex</font> dependency, and four separately '
    'hunted for tenant-isolation violations without finding a single one.'))
story += make_table(
    ['ID', 'Coverage area', 'Key result'],
    [
        ['Z1', 'Bootstrap, config, DB, migrations, Docker', 'Three competing schema authorities; default JWT secret; BD-to-Egypt provenance'],
        ['Z2', 'Agent, LLM client/gateway, concurrency, prompts', 'LLM gateway is dead code; autoflush duplicates every message in context'],
        ['Z3', 'Language engine, Arabizi, orders, style learner', 'Three critical NLP defects; phone numbers corrupted by transliteration'],
        ['Z4', 'API: auth, conversations, customers, orders, products, webhook', '31 endpoints; tenant isolation solid; rate limiting unused'],
        ['Z5', 'API: crawl, dashboard, facebook, postiz, scheduling, tenants', '48 endpoints; Postiz singleton; crawl SSRF; unauthenticated dashboards'],
        ['Z6', 'SQLAlchemy models, Pydantic schemas', '18 models; 3 tables have no schema authority; column drift'],
        ['Z7', 'Auth, tenant, owner-chat, order, product services', 'Owner chat unreachable; order API never auto-dispatched'],
        ['Z8', 'FB/WA/Messenger services, STT, vision, importers', 'WhatsApp media silently dead; no WA/IG onboarding path'],
        ['Z9', 'Knowledge crawler, indexer, retriever, tree sync', 'PageIndex missing from repo; flat fallback on 100% of crawls'],
        ['Z10', 'Middleware, SSRF guard, security utils, phone/address', '25-finding register; every enforcement layer unwired'],
        ['Z11', 'Publishers, Celery, admin panel, Jinja dashboard', 'Publish race; admin broken in three ways; dashboard XSS'],
        ['Z12', 'Test suites and documentation accuracy', '452 tests; ~23% vacuous; suite never green; docs ~50% fiction'],
        ['P1', 'App shell, middleware, design system, deployment', 'Auth theater in middleware; dead tailwind.config; open Caddy proxy'],
        ['P2', 'All 26 marketing and legal pages', '11 stub pages; 6 dead forms; Tavus brand contamination'],
        ['P3', '12 tenant dashboard pages, api-client', 'Entire dashboard is a static mock; api-client dead and broken'],
        ['P4', 'Admin pages, auth pages, stores, hooks', 'Admin = mockup; login form never calls the working BFF route'],
        ['P5', 'BFF routes, Prisma, mini-services, build scripts', 'BFF correct but unwired; Prisma inert; cookie-over-HTTP blocker'],
        ['P6', 'Site components and shadcn/ui kit', '5 orphaned full-Tavus components; 47 of 49 UI files unused'],
        ['X1', 'Cross-repo security audit', '46 findings (10 critical); OWASP 10/10; grades D- / D'],
        ['X2', 'Integration and synthesis', 'Feature reality matrix; 17-call contract audit; combined D+'],
    ],
    [0.06, 0.36, 0.58],
    caption='Table 1: The 20-agent analysis matrix and headline findings per agent.')
story.append(body(
    'All twenty detailed agent reports - including complete function inventories, per-endpoint '
    'catalogs, model field listings, and full vulnerability registers with exploitation scenarios - '
    'are delivered alongside this document as separate markdown files (see the Appendix). This '
    'report deliberately synthesizes rather than repeats them.'))

# ═════════════════════ 3. SYSTEM OVERVIEW ═════════════════════
story += h1_block('3', 'System Overview')
story.append(body(
    'Zemest is positioned as a multi-tenant SaaS offering ready-made AI moderation agents for '
    'small businesses chatting with customers across Facebook Messenger, Instagram Direct, and '
    'WhatsApp. Two specialist personas are marketed: <b>Rabbit v1</b>, an Arabic specialist '
    'covering Egyptian colloquial, Arabizi Latin-script shorthand, and Modern Standard Arabic, and '
    '<b>Rat v1</b>, an English specialist. The intended stack is deliberately free-tier: text '
    'generation on OpenRouter free models or the Gemini free tier, voice notes transcribed locally '
    'with faster-whisper, and product photos analyzed by Gemini 2.0 Flash vision - with graceful '
    'degradation when keys are missing.'))
story.append(body(
    'The backend is a single FastAPI application of roughly 16,300 lines of application code plus '
    '6,800 lines of tests, fronted by approximately 100 routes: 79 JSON API endpoints across 16 '
    'sub-routers, 10 superadmin endpoints, 9 server-rendered Jinja dashboard pages, a sqladmin '
    'instance, and test endpoints. It runs in a seven-service Docker Compose topology (app, '
    'Celery worker, Celery beat, Redis, PostgreSQL 16, and a Postiz sidecar with its own database '
    'and Redis). The platform is a Next.js 16 application served by Bun behind Caddy on port 81, '
    'comprising 26 marketing pages, an 11-page tenant dashboard, a 7-page admin console, four BFF '
    'auth routes, and a Prisma layer that stores nothing.'))
story += chart('diagram.png',
               'Figure 1: The combined Zemest system as verified in code. Red dashed lines mark the '
               'only live inter-repo connection - BFF auth routes to the backend, called by no UI.',
               max_h=430)
story.append(body(
    'Figure 1 makes the central pathology visible: the only wire between the two repositories is '
    'the BFF authentication bridge, which is correct but orphaned. Meta webhooks arrive at the '
    'backend directly; the browser talks to the platform; and the platform never talks to the '
    'backend with user intent. Two dashboards, two admin panels, and zero shared sessions result.'))

# ═════════════════════ 4. BACKEND ARCHITECTURE ═════════════════════
story += h1_block('4', 'Backend Architecture Analysis')
story += h2_block('4.1', 'Bootstrap and the three schema authorities')
story.append(body(
    'Application startup is dominated by a 150-line lifespan function that executes raw DDL - '
    'twenty-nine idempotent <font name="DejaVuSans" size="9">ALTER TABLE</font> statements and five '
    '<font name="DejaVuSans" size="9">CREATE TABLE IF NOT EXISTS</font> blocks - all wrapped in '
    'triple-nested <font name="DejaVuSans" size="9">except Exception: pass</font> handlers, so the '
    'app boots even against an unreachable or divergent database. This creates a third schema '
    'authority alongside SQLAlchemy ORM metadata and Alembic migrations. The three disagree: '
    'the lifespan DDL creates <font name="DejaVuSans" size="9">ip_bans</font> without the '
    '<font name="DejaVuSans" size="9">is_active</font> column the ORM expects (crashing the ban '
    'API), and <font name="DejaVuSans" size="9">admin_audit_log</font> without '
    '<font name="DejaVuSans" size="9">user_agent</font> (silently dropping audit attributes). '
    'Worse, three tables - <font name="DejaVuSans" size="9">scheduled_posts</font>, '
    '<font name="DejaVuSans" size="9">post_insights</font>, and '
    '<font name="DejaVuSans" size="9">blocked_users</font> - are created by no authority at all, '
    'meaning the entire twelve-endpoint scheduling feature 500s on any fresh production install. '
    'The test suite masks all of this because conftest runs '
    '<font name="DejaVuSans" size="9">Base.metadata.create_all</font> against SQLite.'))
story += h2_block('4.2', 'Configuration and database')
story.append(body(
    'The configuration system exposes thirty-five pydantic-settings entries with environment '
    'overrides, but security-sensitive defaults are dangerous: '
    '<font name="DejaVuSans" size="9">JWT_SECRET_KEY</font> defaults to the string '
    '"change-me-to-a-random-secret-key" and is reused for signing session cookies and the sqladmin '
    'session; nothing checks <font name="DejaVuSans" size="9">APP_ENV</font> to refuse boot in '
    'production on default secrets. Access tokens live 24 hours with no revocation path, because '
    'the refresh-token and denylist machinery in the security utils is never wired to any route. '
    'The database layer is otherwise competent async SQLAlchemy 2.0: ownership-scoped session '
    'dependency injection, correct session-per-request lifecycle. Two production risks stand out: '
    'no <font name="DejaVuSans" size="9">pool_pre_ping</font> or '
    '<font name="DejaVuSans" size="9">pool_recycle</font> against the thirty-connections-per-process '
    'pool (three processes against PostgreSQL\'s default one hundred), and '
    '<font name="DejaVuSans" size="9">get_db</font> commits in post-yield teardown - after the '
    'response is sent - so failed commits surface as silent 200s.'))
story += h2_block('4.3', 'Migrations reveal the product lineage')
story.append(body(
    'The Alembic lineage tells a story the README does not. The initial schema ships Bangladeshi '
    'commerce constructs: a <font name="DejaVuSans" size="9">name_bn</font> product column and '
    'division/district/upazila geography. The second migration destructively drops nine product '
    'columns while introducing a flexible attributes JSON blob - without backfilling data. The '
    'third, titled "egypt_pivot", renames the Bangladeshi geography to Egyptian governorates, adds '
    'Instagram and WhatsApp channels, Cairo delivery fees, thirteen tenant settings columns, and '
    'hot-path indexes. Its docstring claims a unique constraint on '
    '<font name="DejaVuSans" size="9">fb_message_id</font> for webhook idempotency; the code '
    'creates a plain index, and the ORM declares nothing - so the dedup check remains a racy '
    'SELECT-then-insert. Type drift persists across authorities on four order columns.'))
story += h2_block('4.4', 'Deployment and dependencies')
story.append(body(
    'Docker Compose orchestrates seven services with healthcheck gating and a non-root runtime '
    'user, but zero resource limits, a host-exposed unauthenticated Redis (wiping rate limits, '
    'Celery state, and any future JWT denylist on restart), a '
    '<font name="DejaVuSans" size="9">postiz:latest</font> sidecar launched with '
    '<font name="DejaVuSans" size="9">NOT_SECURED=true</font> and open registration, and a likely '
    'Playwright bug - browsers install under <font name="DejaVuSans" size="9">/root/.cache</font> '
    'while the runtime user is <font name="DejaVuSans" size="9">appuser</font>. The requirements '
    'file has no lockfile; <font name="DejaVuSans" size="9">python-jose 3.3.0</font> carries '
    'CVE-2024-33663/33664 (fixed in 3.4.0); passlib is unmaintained; and all five test tiers '
    '(locust, mutmut, schemathesis, playwright, hypothesis) ship in the production image.'))

# ═════════════════════ 5. AI ENGINE ═════════════════════
story += h1_block('5', 'AI Engine Analysis')
story += h2_block('5.1', 'The live agent pipeline')
story.append(body(
    'A customer message arriving at the webhook triggers a fourteen-step pipeline that runs inline '
    'in the request - not offloaded to Celery: voice transcription via faster-whisper, Gemini '
    'vision analysis of up to three images, customer upsert, Meta-retry deduplication, '
    'conversation reuse with no expiry window, message persistence, last-ten-message history '
    'loading, knowledge retrieval, multi-dialect language detection with Arabizi transliteration, '
    'dialect-aware persona prompt selection (nine personas; Rabbit for Arabic, Rat for English), '
    'context assembly, the LLM call itself, in-band JSON order extraction, and reply persistence '
    'with token-usage accounting. "Tools" are prompt-engineered JSON contracts rather than function '
    'calling. The design is coherent; the implementation carries several verified defects.'))
story.append(bullet(
    '<b>Autoflush duplication.</b> SQLAlchemy autoflush inserts the current customer message '
    'before history is loaded, so every LLM call sees the same message twice - wasted tokens and '
    'inflated billing on every single turn.'))
story.append(bullet(
    '<b>Dead concurrency governance.</b> The entire research-document recommendation set - LiteLLM '
    'router gateway, per-tenant rate limits, Redis daily quotas, semaphore concurrency gates, cost '
    'tracking - exists only as never-imported code. Production has zero rate limiting or cost '
    'ceilings; one busy tenant can exhaust the shared OpenRouter free tier for everyone. The '
    'gateway is unimportable anyway: <font name="DejaVuSans" size="9">aiolimiter</font> is missing '
    'from requirements and its Ollama fallback host has no service.'))
story.append(bullet(
    '<b>Paid fallbacks on a "free-only" stack.</b> The live chain is '
    '<font name="DejaVuSans" size="8.5">meta-llama/llama-4-maverick:free</font> then '
    '<font name="DejaVuSans" size="8.5">gemini-2.0-flash-001</font> then '
    '<font name="DejaVuSans" size="8.5">qwen-2.5-72b-instruct</font> - two of three fallbacks are '
    'paid models with no budget guard, and each call opens a fresh HTTP client.'))
story.append(bullet(
    '<b>Order integrity.</b> Hallucinated product names match nothing and create order items at '
    'unit price zero; <font name="DejaVuSans" size="9">ilike</font> wildcards are unescaped; '
    'quantity is unvalidated.'))
story.append(bullet(
    '<b>Injection surface.</b> No defenses at either layer: customer text and crawled - '
    'attacker-influenced - catalog content are spliced raw into the system prompt. The dedicated '
    'injection detector exists and is wired to nothing.'))
story += h2_block('5.2', 'Language engine: three verified pipeline defects')
story.append(body(
    'The multi-dialect engine classifies Arabic, Arabizi, English, and mixed input via script '
    'ratios, digit-phoneme presence, and optional camel_tools dialect ID, then transliterates '
    'Arabizi to Arabic before the LLM call. Executable verification exposed three defects in the '
    'highest-value flows. First, ordinary English containing digits ("size 7 please") classifies '
    'as Arabizi with 0.75 confidence, selecting the wrong persona and triggering transliteration. '
    'Second, the transliteration map replaces digit keys globally, so a phone number like '
    '01012345678 becomes unreadable phoneme garbage ("0101..."), breaking phone and address '
    'collection in the flagship Arabizi ordering flow. Third, the chat-history import path '
    'creates a Conversation with a null customer_id against a NOT NULL column, guaranteeing an '
    'IntegrityError on the style-learning import endpoint. Separately, the curated 200-word '
    'arabizi_map module is one hundred percent dead code, and the style learner writes plural '
    'profile keys where the prompt builder reads singular ones - only "tone" ever reaches the '
    'customer-facing prompt, silently disabling learned style.'))

# ═════════════════════ 6. API LAYER ═════════════════════
story += h1_block('6', 'API Layer Analysis')
story.append(body(
    'The API surface spans 79 endpoints across sixteen router files, plus ten superadmin '
    'endpoints and nine Jinja dashboard routes. The table below consolidates the catalog '
    'produced by agents Z4 and Z5; complete per-endpoint tables with parameters, response '
    'schemas, and status codes are in their detailed reports.'))
story += make_table(
    ['Router', 'Prefix', 'Endpoints', 'Auth', 'Notable findings'],
    [
        ['auth', '/api/auth', '4', 'public', 'Login/register/FB/me; no refresh; no rate limit'],
        ['webhook', '/api/webhook', '6', 'HMAC', 'Best file: fail-closed constant-time verification, fast-ACK, dedup sentinel; no retry/DLQ'],
        ['conversations', '/api/tenants/{id}/conversations', '2', 'JWT+tenant', 'Solid; pagination via selectinload'],
        ['customers', '/api/tenants/{id}/customers', '3', 'JWT+tenant', 'N+1: three aggregate queries per row (151/page)'],
        ['orders', '/api/tenants/{id}/orders', '7', 'JWT+tenant', 'Create always 500s (MissingGreenlet); retry-api can duplicate real orders'],
        ['products', '/api/tenants/{id}/products', '7', 'JWT+tenant', 'import-url SSRF; O(n^2) CSV import'],
        ['test_chat', '/api/test', '2', 'none', 'Runs real AI pipeline + writes real rows; not production-safe'],
        ['crawl', '/api/tenants/{id}/crawl', '3', 'JWT+tenant', 'SSRF incl. file://; Celery race (dispatch before commit)'],
        ['dashboard', '/dashboard', '9', 'none', 'All HTML pages unauthenticated; tenant enumeration surface'],
        ['facebook', '/api/facebook', '3', 'JWT', 'Tokens in query strings; sync-catalog broken (kwargs TypeError)'],
        ['postiz', '/api/tenants/{id}/postiz', '12', '10 JWT', 'Process-wide singleton session - any tenant can hijack'],
        ['scheduling', '/api/tenants/{id}', '8', 'JWT+tenant', 'Real state machine; tz-naive datetimes break Cairo scheduling'],
        ['style_learning', '/api/tenants/{id}', '3', 'JWT+tenant', '500 MB upload buffered in RAM before size check'],
        ['tenants', '/api/tenants', '5', 'JWT+tenant', 'PATCH cannot clear fields'],
        ['address', '/api/address', '5', 'public', 'shipping endpoint guaranteed 500 (float of dict)'],
        ['admin (REST)', '/api/admin', '10', 'superadmin JWT', 'Ban CRUD 500s (invalidate_all missing); analytics over never-written table'],
    ],
    [0.13, 0.21, 0.08, 0.11, 0.47],
    caption='Table 2: Backend API surface by router. "JWT+tenant" = bearer token plus ownership-scoped '
            'tenant dependency. Every tenant-scoped route funnels through the same get_tenant check.',
    align_center_cols={2})
story.append(body(
    'The layer\'s crown jewel is tenant isolation: every tenant route passes through an '
    'ownership-scoped dependency (<font name="DejaVuSans" size="9">Tenant.owner_id == user.id</font>) '
    'plus per-query filters, and four independent agents hunting for IDOR found zero instances. '
    'The layer\'s systemic weakness is production hardening: slowapi rate limiting is installed '
    'but no endpoint uses it (login, register, and webhooks are unthrottled), the JWT refresh and '
    'revocation system is dead code, and the webhook\'s fast-ACK design silently drops messages '
    'when processing fails - no retry, no dead-letter queue, no at-least-once semantics.'))

# ═════════════════════ 7. DATA MODELS ═════════════════════
story += h1_block('7', 'Data Model and Schema Analysis')
story.append(body(
    'Eighteen SQLAlchemy models map to eighteen tables, with 28 Pydantic schema classes layered '
    'above. The domain modeling is genuinely thoughtful for the Egyptian market: a 27-governorate '
    'address hierarchy with per-tenant inside/outside-Cairo shipping rates and free-shipping '
    'thresholds, flexible product attributes via an allow-extra JSON contract, token usage '
    'tracking per LLM call, and a real order state machine (pending to confirmed to shipped to '
    'delivered, plus cancelled, with illegal transitions rejected).'))
story += make_table(
    ['Issue', 'Evidence', 'Impact'],
    [
        ['3 tables created by no authority', 'scheduled_posts, post_insights, blocked_users absent from Alembic and lifespan DDL', 'Scheduling + superadmin blocking 500 on fresh installs'],
        ['ORM vs DDL column drift', 'ip_bans.is_active, admin_audit_log.user_agent, user_sessions.browser exist only in ORM', 'Admin API crashes; audit writes fail silently'],
        ['fb_message_id not unique', 'Plain index in migration; no ORM constraint; SELECT-then-insert dedup', 'Concurrent Meta retries produce duplicate AI replies and orders'],
        ['Type drift on 4 order columns', 'payment_phone_last2, payment_trx_id, api_status, api_external_id lengths differ', 'Runtime truncation or migration/ORM divergence'],
        ['Global order_number uniqueness', 'ORD-YYMMDD-rand(100-999) vs UNIQUE column', '~50% IntegrityError/day at 35 orders; AI-path failures are silent'],
        ['users.email not unique', 'No unique constraint; scalar_one_or_none on login', 'Registration race permanently 500s login for that email'],
        ['Pydantic layer has zero validators', 'No field_validator/Literal anywhere; unbounded quantity and unit_price', 'Validation gaps pushed entirely to handlers'],
        ['Dead weight', 'Tenant.knowledge_base JSON never read; SiteUser unused; UserSession never written', 'Analytics perpetually zero; schema confusion'],
    ],
    [0.26, 0.42, 0.32],
    caption='Table 3: Data-integrity findings from model analysis (agent Z6).')
story.append(body(
    'Tenant scoping is achieved purely through query discipline - eight tables directly carry '
    'tenant_id, three indirectly - with no model-level guard such as loader criteria or row-level '
    'security. The discipline held under audit, but it is one careless query away from breaking, '
    'and the globally-unique order_number is already a cross-tenant collision generator.'))

# ═════════════════════ 8. SERVICES LAYER ═════════════════════
story += h1_block('8', 'Services Layer Analysis')
story += h2_block('8.1', 'Business services: two flagship features are dormant')
story.append(body(
    'The owner-chat subsystem is the product\'s hidden gem - page owners DM their own bot in '
    'Egyptian Arabic to update prices, pause products, add products, or query today\'s orders, '
    'parsed entirely by LLM into JSON commands with server-side execution. It is also unreachable: '
    '<font name="DejaVuSans" size="9">tenant.owner_psid</font> is read at exactly one webhook '
    'branch but written by no API, no service, no admin panel, and not even the seed script. '
    'Similarly, the external order-receiving bridge ("Inventory Connect", marketed as a named '
    'product) never auto-dispatches: despite an "after order is created" docstring, '
    '<font name="DejaVuSans" size="9">call_order_api</font> is invoked only by a manual retry '
    'endpoint - which lacks an idempotency guard and happily re-submits already-successful '
    'orders, duplicating real-world fulfillment. The bridge also carries its own SSRF: a '
    'tenant-configurable URL with no scheme or private-IP validation, whose response body is '
    'stored and surfaced back to the dashboard.'))
story += h2_block('8.2', 'Channel services: WhatsApp is a facade')
story.append(body(
    'The Messenger path is polished; the WhatsApp path is theater. The WhatsApp webhook places '
    'media IDs into fields that the transcription and vision services treat as HTTP URLs - no '
    'media download call exists anywhere - so every WhatsApp voice note and image analysis '
    'throws and is swallowed. More fundamentally, the WA and IG channels have no onboarding '
    'path at all: phone number IDs, access tokens, and Instagram user IDs exist as columns but '
    'appear in no Pydantic schema and are settable by no endpoint, so both webhooks can only '
    'ever match manually database-seeded tenants. Additional verified issues: Celery '
    'notification tasks dispatch before the session commits (workers find no order and silently '
    'skip), Graph API v21.0 is past its two-year guarantee with the WhatsApp version separately '
    'hardcoded, Meta tokens travel in query strings throughout, the 464 MB whisper model '
    'downloads inside the webhook request path on first use, and the Messenger history importer '
    'double-parses its ZIP while the WhatsApp importer reads US-order dates that transpose day '
    'and month on Egyptian exports.'))

# ═════════════════════ 9. KNOWLEDGE ENGINE ═════════════════════
story += h1_block('9', 'Knowledge Engine (RAG) Analysis')
story.append(body(
    'The knowledge subsystem is architectured as a cost-conscious TOC-navigation RAG: crawl the '
    'tenant website with Playwright plus trafilatura, build an LLM-summarized tree of knowledge '
    'nodes, and at question time make one LLM call that reads the tree\'s table of contents and '
    'selects up to three nodes for context. The headline discovery is that the flagship '
    'component is missing: <font name="DejaVuSans" size="9">indexer.py</font> imports '
    '<font name="DejaVuSans" size="9">lib/pageindex</font>, which does not exist in the '
    'repository. The import always fails, the exception is swallowed, and a flat fallback tree '
    'of bare titles runs on one hundred percent of crawls - no summaries, no hierarchy, no node '
    'types. Every crawl logs a zero-token usage row. The entire knowledge-tree story in the '
    'documentation is aspirational.'))
story.append(body(
    'This is lexical selection, not embedding RAG - no vectors, no BM25, and pg_trgm used only '
    'for product deduplication (against a GIN index built on a different expression, so it '
    'cannot even be used). Two retrieval bugs were confirmed by executable simulation: '
    'category double-counting appends every product under a selected category twice to the '
    'prompt context, and ID padding zero-fills integers but not the strings the LLM actually '
    'returns, so a model answering with string IDs matches nothing and context silently '
    'degrades to empty. A fully written Arabic-aware lexical fallback '
    '(<font name="DejaVuSans" size="9">search_relevant_products</font>) sits dead with zero '
    'callers. Re-crawls wholesale-replace the knowledge tree, wiping product nodes that only '
    'survive because product extraction re-runs afterwards. Security-wise the crawler accepts '
    '<font name="DejaVuSans" size="9">file://</font> URLs through Chromium, runs Katana through '
    'the Docker socket (root-equivalent), has no robots.txt handling, no politeness delay on the '
    'httpx path, and truncates twenty crawled pages to six thousand characters - roughly 85 '
    'percent of the crawl never reaches the LLM.'))

# ═════════════════════ 10. MIDDLEWARE & SECURITY ═════════════════════
story += h1_block('10', 'Middleware and Security Analysis')
story.append(body(
    'Seven middleware files wrap the application in the order SecurityHeaders, RateLimit, '
    'BotDetection, IPBan, Session (the source comment claims a different order). Only three '
    'classes actually run, and only two do anything observable. The security posture paradox is '
    'summarized by agent Z10 as "high-quality code wrapped around a disconnected security '
    'architecture": of the five fully-built defenses, every single one is unwired.'))
story += make_table(
    ['Finding', 'Severity', 'Evidence'],
    [
        ['SSRF guard is dead code', 'Critical', 'SafeHTTPClient with redirect re-validation, scheme allowlist, ten blocked networks - zero app importers; crawl, import-url, and order bridge fetch raw user URLs'],
        ['IP banning triple-broken', 'Critical', 'Middleware runs with empty sets; ip_bans table never loaded; admin calls IPBanMiddleware.invalidate_all() which does not exist (AST-proven) - ban CRUD 500s'],
        ['Prompt-injection defense unwired', 'Critical', 'Detector + sanitizer never called by agent or webhook; customer text and crawled content reach the LLM raw; tests mock the agent so they pass vacuously'],
        ['Rate limiting is a no-op', 'Critical', 'SlowAPI middleware installed, no endpoint decorated, no default limits; login and webhooks unthrottled; xfail tests codify this as expected'],
        ['JWT/session secret reuse', 'High', 'Default "change-me..." secret signs JWTs, session cookies, and sqladmin; python-jose 3.3.0 CVEs; tokens unrevokable for 24h'],
        ['Shipping endpoint 500', 'High', 'float(dict) proven by execution on /api/address/shipping'],
        ['Divergent duplicate validators', 'High', 'Two phone validators disagree; order pipeline rejects 00201... numbers the other accepts - silent order drops'],
        ['IPv6 bypasses', 'Medium', 'IPv4-mapped IPv6 and NAT64 literals proven to bypass both SSRF blocklists; DNS-rebinding TOCTOU in validate-then-fetch'],
    ],
    [0.24, 0.10, 0.66],
    caption='Table 4: Selected findings from the 25-entry middleware/security register (agent Z10), '
            'consolidated with cross-repo audit results.', align_center_cols={1})
story.append(body(
    'What is genuinely good and live: the security-headers middleware (CSP, conditional HSTS, '
    'COOP, CORP, pure ASGI, header deduplication), constant-time fail-closed webhook signature '
    'verification, algorithm-pinned JWT decoding, and bcrypt at twelve rounds. The recommendation '
    'is not to write new security code - it is to delete the duplicated weak copies and connect '
    'the strong ones that already exist.'))

# ═════════════════════ 11. SCHEDULING, TASKS, ADMIN ═════════════════════
story += h1_block('11', 'Scheduling, Tasks, and Admin Analysis')
story += h2_block('11.1', 'Publishers and Celery')
story.append(body(
    'The scheduling subsystem implements sixteen Graph API functions across Facebook and '
    'Instagram publishers, including the two-step IG media container pattern with 150-second '
    'status polling and a best-time-to-post heatmap from online followers. Reliability is thin: '
    'all publishers share bare-Exception handling with no status-code checks (non-JSON responses '
    'crash as decode errors), zero retries, fresh HTTP clients per call, and access tokens in '
    'query strings. Instagram stories and carousels are doubly broken by a container-type bug '
    'and an unreachable branch. Celery runs one two-slot worker with no queues or routing, so '
    '600-second crawls share capacity with minute-cadence publishing and order emails; declared '
    'max_retries are dead because <font name="DejaVuSans" size="9">self.retry()</font> is never '
    'called; the publish claim lacks FOR UPDATE SKIP LOCKED (a duplicate-publish window); and '
    'failed posts are terminal, stranding rows in "publishing" forever on worker crash.'))
story += h2_block('11.2', 'Three admin surfaces, three failure modes')
story.append(body(
    'The backend ships three administration surfaces, each broken differently. sqladmin at '
    '/_admin works but never re-validates adminship after login and its UserAdmin writes '
    'plaintext into the hashed_password column. The custom REST admin API requires superadmin '
    'bearer tokens but its ban CRUD crashes on the nonexistent invalidate_all method, its '
    'analytics endpoints read a user_sessions table no code ever writes, and audit-log inserts '
    'fail on missing columns. The custom admin dashboard HTML is quadruply broken: Bearer-gated '
    'so no browser can view it, fetching a nonexistent analytics endpoint, expecting response '
    'shapes the API never returns, and sending cookie auth to JWT endpoints. The tenant-facing '
    'Jinja dashboard - the only UI in either repository that actually works - is nonetheless '
    'unauthenticated by design across all nine pages, ships demo credentials on its login '
    'screen, and carries confirmed stored XSS in the dashboard and chat templates (unescaped '
    'tenant and customer names, unsanitized markdown rendering).'))

# ═════════════════════ 12. TESTS & DOCS ═════════════════════
story += h1_block('12', 'Test Suite and Documentation Analysis')
story.append(body(
    'The test suite is unusually ambitious for a prototype: 452 collected tests across seven '
    'tiers - unit/integration, property-based (hypothesis), security (IDOR, JWT attacks, SQL '
    'injection, XSS, SSRF, prompt injection, rate limiting), scraper resilience, e2e flows, '
    'load (locust), and OpenAPI contract (schemathesis). Executing it with pinned dependencies '
    'yielded 418 passed, 10 failed, 14 skipped, 3 xfailed, and 8 errors - the suite has never '
    'been green, and no CI exists anywhere to notice.'))
story += stat_row([
    ('452', 'Collected tests'),
    ('~23%', 'Vacuous or dead-certifying'),
    ('8+10', 'Errors + failures measured'),
    ('0', 'CI pipelines'),
])
story.append(body(
    'Approximately fifty tests are outright vacuous: five "end-to-end" security tests mock '
    '<font name="DejaVuSans" size="9">process_customer_message</font> and then assert on the '
    'mock\'s own hardcoded string, one e2e test contains no assertion at all, and another\'s key '
    'check is literally <font name="DejaVuSans" size="9">if x not in body: pass</font>. Another '
    'fifty-two tests certify dead defenses - they exercise the rate limiter, the SSRF guard, and '
    'the injection detector that no production code imports. The conftest\'s create_all-on-SQLite '
    'strategy masks every migration bug (ten scheduling tests pass while production installs '
    'crash). The schema tier is triple-broken by version incompatibilities in every direction. '
    'And the genuinely strong parts deserve mention: the thirteen IDOR tests and seventeen '
    'JWT-attack tests are real and rigorous, and the property-based totality tests are solid.'))
story.append(body(
    'Running the long-ignored security tests surfaced a previously unknown production bug: '
    '<font name="DejaVuSans" size="9">POST /api/tenants/{id}/orders</font> always returns 500 - '
    'the response serializer lazy-loads <font name="DejaVuSans" size="9">order.items</font> in '
    'an async context after the service inserted items without populating the relationship '
    '(MissingGreenlet). Manual order creation is broken in production today; only red, skipped '
    'tests detect it. Documentation fares worse: agents rated the README and MASTER_PROMPT '
    'roughly fifty percent fiction - the Rabbit/Rat "models" are GPT wrappers, webhooks process '
    'inline rather than via Celery, and the referenced .env.example and LICENSE files do not '
    'exist.'))

# ═════════════════════ 13. FRONTEND APP SHELL ═════════════════════
story += h1_block('13', 'Frontend App Shell and Design System')
story.append(body(
    'The platform runs Next.js 16 (the App Router, despite the README saying 15) on Bun with a '
    'standalone output build. The root layout mounts three font families - Inter, Instrument '
    'Serif, and JetBrains Mono - full SEO and OpenGraph metadata, and, curiously, two independent '
    'toast systems, neither of which is ever triggered. The landing page is a clean server '
    'component composing eleven fully client-side sections. The design system is the repo\'s '
    'crown jewel: forty-five plus coherent tavus-prefixed CSS tokens implement a neo-brutalist '
    'language of terminal-black three-pixel borders, hard offset shadows, retro OS-window chrome, '
    'and a rich bitmap-effects family (halftone, dither, scanline) built entirely from gradients '
    'with no image assets. Tailwind v4\'s CSS-first configuration is used correctly in '
    'globals.css, which also means the checked-in tailwind.config.ts is dead code. Dark mode is '
    'structural fiction - the .dark block is a verbatim copy of :root with no toggle anywhere.'))
story.append(body(
    'The platform\'s middleware is auth theater. It checks only for the presence of the '
    'zemest_auth cookie - no signature, no expiry - and also accepts a legacy Supabase cookie '
    'from a stack that is not used; any client-set cookie value bypasses the redirect. The '
    '/admin superadmin gate at middleware.ts:44-48 is an empty comment block. The '
    'redirect parameter is captured and consumed by zero files. Meanwhile the BFF login route '
    'correctly sets httpOnly cookies - but the login form never calls it. Deployment '
    'configuration adds risk: <font name="DejaVuSans" size="9">ignoreBuildErrors: true</font> '
    'masks what would otherwise be build-failing bugs, strict mode is off, and the Caddyfile '
    'contains an open-proxy XTransformPort rule that will forward to arbitrary ports.'))

# ═════════════════════ 14. MARKETING SITE ═════════════════════
story += h1_block('14', 'Marketing Site Analysis')
story.append(body(
    'Agent P2 classified all twenty-six marketing pages: ten carry real Zemest content, five are '
    'wholesale Tavus leftovers, and eleven are literal placeholder stubs - including all four '
    'solutions sub-pages, meaning the primary conversion funnel dead-ends on unfinished pages '
    'shipping "TITLE - Zemest" metadata that is crawlable. The Tavus contamination is extensive: '
    'the careers page title tag literally reads "Tavus - The Human Computing Company" with San '
    'Francisco roles, the blog is nineteen hardcoded Tavus posts whose links all 404 (no blog '
    'slug route exists), and the research page showcases Tavus papers.'))
story += make_table(
    ['Form', 'What actually happens', 'User impact'],
    [
        ['Login / Get started', 'onSubmit = preventDefault() - the working BFF route is never called', 'Cannot authenticate via email'],
        ['Register', 'Client-side validation passes, then window.location to /dashboard with no API call', 'Middleware bounces to /login; drop the redirect param'],
        ['Forgot password', 'Fake "reset link sent" confirmation', 'Deceptive - no reset route exists anywhere'],
        ['Book a demo', 'Fake success screen, no network call', 'Zero lead capture'],
        ['Newsletter (blog)', 'No handler at all', 'Dead control'],
        ['Facebook OAuth', 'Redirects to Meta with demo_client_id and a callback route that does not exist', '404 dead-end; no CSRF state param'],
    ],
    [0.20, 0.44, 0.36],
    caption='Table 5: All six marketing-site forms are dead or fake - the site cannot generate a single lead.')
story.append(body(
    'Compliance claims are made without artifacts: the enterprise page sells SOC 2 Type II, '
    'HIPAA BAAs, GDPR/EU residency, a 99.95% SLA, and thirty-minute incident response, while the '
    'DPA, trust, and status pages are placeholders and the backend contains no billing, quota, '
    'or SLA machinery whatsoever. The logos section ships real Amazon, Salesforce, Deloitte, CVS '
    'Health, and Frame logos under "Powering moderation for 100,000+ sellers" - a fabricated '
    'endorsement with real legal exposure. The conversational demo on the landing page is '
    'scripted theater: a hardcoded six-message array advanced by setInterval, a fake LIVE badge, '
    'dead microphone buttons, and the "<3s replies" claim repeated three times with no latency '
    'machinery anywhere in the stack.'))

# ═════════════════════ 15. DASHBOARD ═════════════════════
story += h1_block('15', 'Tenant Dashboard Analysis')
story.append(body(
    'The tenant dashboard - twelve files, roughly 2,700 lines - is a pixel-perfect static '
    'prototype. Every page renders module-scope mock arrays; grep proves zero fetch calls across '
    'the entire dashboard. Every action button is inert: CREATE ORDER\'s onClick closes its own '
    'modal, START CRAWL resets its own form, every SAVE CHANGES and EXECUTE does nothing. The '
    'chat playground simulates AI replies with a 1200-millisecond setTimeout and canned strings '
    'rather than calling the genuinely working test-chat endpoint - its debug panel even '
    'displays field names (conversation_id, tokens_used) that map one-to-one onto the backend\'s '
    'TestChatResponse, proving the wiring was scoped and then never done.'))
story.append(body(
    'The api-client module is both dead and architecturally broken. It has zero importers. Even '
    'if wired, it sends cookies via credentials:include directly to the FastAPI origin, but the '
    'backend authenticates exclusively via HTTPBearer headers and has no CORS middleware - every '
    'call would fail preflight or 401. Its coverage is only seven of roughly fifteen backend '
    'router groups, it cannot send multipart uploads despite UI buttons for CSV import, and its '
    'refresh-token logic references a field the backend never returns. A latent Next.js 16 bug '
    'compounds all of this: all client pages access params.tenantId synchronously where the '
    'framework now requires React.use() unwrapping - masked today only by '
    'ignoreBuildErrors. Dashboard tenant cards link to mock IDs like tnt_001 that the '
    'backend\'s UUID validation would reject outright.'))

# ═════════════════════ 16. ADMIN & AUTH ═════════════════════
story += h1_block('16', 'Admin and Authentication Analysis')
story.append(body(
    'The seven-page admin console is a fully designed mockup: the only imports across all pages '
    'are React, Next Link, and lucide-react icons - zero fetches, zero stores, zero React Query. '
    'User view/block/unblock buttons have no onClick handlers even though the backend block '
    'endpoints exist; the health page\'s REFRESH button runs a fake 800-millisecond spinner next '
    'to a fabricated "Gemini Vision DOWN" status; the audit-log CSV exporter - the only real '
    'code on any admin page - exports the mock data. Backend response shapes mismatch the mock '
    'structures throughout (UUIDs where emails are displayed, different field names), and the '
    'sessions page reads a table the backend never writes.'))
story.append(body(
    'Authentication is a facade with one honest corner. The BFF routes correctly forward '
    'credentials and set httpOnly cookies - and nothing calls them. The login form is a '
    'preventDefault stub; register redirects without authenticating; forgot-password fabricates '
    'a success message; Google and SSO buttons are dead; and the Facebook OAuth flow dead-ends '
    'at a callback route that does not exist, with a demo client ID and no CSRF state parameter. '
    'Both Zustand stores have zero importers, so no token ever reaches client state and the '
    'is_superadmin flag has no source. The logout link navigates without clearing cookies. On '
    'the backend side of the same flow, the login endpoint accepts Facebook tokens from any app '
    'without debug_token verification and links accounts by user ID only, creating duplicate '
    'accounts for the same human.'))

# ═════════════════════ 17. BFF & DATA LAYER ═════════════════════
story += h1_block('17', 'BFF and Data Layer Analysis')
story.append(body(
    'The four BFF routes (login, register, logout, facebook) implement the '
    'Backend-for-Frontend pattern correctly: they forward credentials to the FastAPI origin, '
    'return a success envelope, and stash the JWT in an httpOnly, lax, secure-in-production '
    'cookie with 24-hour or 30-day remember-me expiry. This is the right architecture, and it '
    'is unwired. The refresh cookie is never set because the backend never returns a refresh '
    'token; the 30-day cookie therefore wraps a 24-hour JWT. The Facebook route is the only '
    'OAuth path with a caller, and it terminates at the nonexistent callback.'))
story.append(body(
    'Prisma is inert scaffold: template User and Post models with no relations, an empty '
    'committed SQLite database, no migrations, and a db.ts client that zero files import. The '
    'platform\'s own data store owns nothing - PostgreSQL on the backend is the sole real '
    'source of truth, with a latent identity-schema drift (cuid vs UUID user ids) if the '
    'scaffold is ever activated. The mini-services directory is an empty convention: per-folder '
    'Bun services bundled and routed through Caddy\'s transform rule. The strongest code in the '
    'repository is the deployment pipeline - eight shell scripts implementing standalone builds '
    'with self-healing configuration injection, a vendored Python runtime, artifact packaging, '
    'and pipeline self-tests. One deployment blocker deserves headline billing: production sets '
    'secure cookie flags while Caddy serves plain HTTP on port 81, so browsers will refuse the '
    'auth cookie and production login cannot persist at all as configured.'))

# ═════════════════════ 18. SECURITY AUDIT ═════════════════════
story += h1_block('18', 'Cross-Repository Security Audit')
story.append(body(
    'The capstone security audit consolidated every finding from all agents into a 46-entry '
    'register, re-verified the headline claims directly in source, mapped them against the OWASP '
    'Top 10 (all ten categories are affected), and produced three end-to-end attack narratives: '
    'an external attacker hijacking a tenant\'s bot through the Postiz session or stored XSS; an '
    'SSRF chain from the crawl API through file:// reads and the Docker socket into the internal '
    'network and credentials; and cross-tenant access via the shared Postiz session or the '
    'default JWT secret. The register breaks down as follows.'))
story += chart('chart_vulns.png',
               'Figure 2: Consolidated vulnerability register by severity - 46 findings from the '
               'cross-repo security audit (agent X1).', max_h=215)
story.append(body(
    'Security posture grades: the backend earns D- (3/10) - exemplary SQL-layer tenant isolation '
    'and constant-time webhook verification, but five fully-built defenses disconnected, three '
    'SSRF surfaces, a forgeable default secret, a cross-tenant singleton, stored XSS, and an '
    'unthrottled login. The platform earns D (4/10) - a correct BFF cookie pattern undermined by '
    'presence-only middleware theater, no admin gate, and an open reverse-proxy rule. Deployed '
    'together as configured, the combined system would rate F. The audit\'s defining observation '
    'mirrors the middleware analysis: this codebase builds excellent security machinery and then '
    'never connects it - wiring existing code, rather than writing new code, closes most of the '
    'critical gaps in roughly two to three engineer-weeks.'))
story += make_table(
    ['P0 must-fix', 'Effort'],
    [
        ['Secrets bootstrap: refuse boot on default JWT_SECRET_KEY; separate session signing secret', '0.5 day'],
        ['Delete the Caddy XTransformPort open-proxy rule', '0.1 day'],
        ['Wire the existing SSRF guard into crawl / import-url / order-bridge; block file:// and private IPs; stop returning raw upstream bodies', '3-5 days'],
        ['Per-tenant Postiz sessions to replace the process-wide singleton', '2 days'],
        ['Escape dashboard templates + sanitize markdown; default rate limits and login lockout; authenticate the 9 dashboard routes; remove shipped demo credentials', '3-4 days'],
    ],
    [0.82, 0.18],
    caption='Table 6: The security audit\'s top five must-fix items (about 2-3 engineer-weeks total).')

# ═════════════════════ 19. INTEGRATION ═════════════════════
story += h1_block('19', 'Integration Analysis')
story.append(body(
    'Agent X2 audited every place the platform could touch the backend - seventeen call sites - '
    'against the actual routes. The verdict: two backend endpoints are provably broken (orders '
    'create always 500s with MissingGreenlet; address shipping always 500s with a TypeError), '
    'the OAuth flow dead-ends at a nonexistent callback route, three analytics responses are '
    'hollow because they read a table no code ever writes, and every platform client function is '
    'dead code anyway. Roughly thirty additional backend endpoints have no platform call site at '
    'all. The naming discipline is the one bright spot - snake_case end to end, so field shapes '
    'match wherever the plumbing exists.'))
story += chart('chart_features.png',
               'Figure 3: Feature reality audit - of 20 marketed or architected features, only '
               'multi-tenant isolation fully works; WhatsApp, the hero channel, is a facade.', max_h=185)
story += make_table(
    ['Feature', 'Backend', 'Frontend', 'Verdict'],
    [
        ['Multi-tenant isolation', 'Zero IDOR in 79 endpoints', 'n/a', 'Works'],
        ['FB Messenger automation', 'Live pipeline, unhardened', 'Simulated chat', 'Partial'],
        ['Voice notes', 'Messenger-only; 464MB model in request path', 'Claim + mock', 'Partial'],
        ['Image understanding', 'Works; blind product matching; re-billed on retries', 'Claim + mock', 'Partial'],
        ['Knowledge crawl / RAG', 'PageIndex missing; flat fallback on 100% of crawls', 'Mock', 'Degraded'],
        ['Order management', 'AI path works; manual create 500s', 'Mock modal', 'Partial'],
        ['Scheduled posting', 'Tables never created in prod; publish race', '439-line mock', 'Partial'],
        ['Postiz integration', 'One session shared across all tenants', 'Mock health row', 'Insecure'],
        ['Instagram automation', 'No onboarding path', 'Stub page', 'Dead'],
        ['WhatsApp automation', 'Media IDs as URLs; no onboarding; one send function', 'Hero imagery', 'Facade'],
        ['Style learning', 'Import crashes; key mismatch', '216-line mock', 'Broken'],
        ['Owner chat commands', 'Full system, unreachable (owner_psid unwritable)', 'Mock toggle', 'Dead code'],
        ['Order API bridge', 'Never auto-dispatched; retry duplicates orders', 'Mock form', 'Dead'],
        ['Admin panel', 'Three surfaces, three failure modes', 'Mockup', 'Broken'],
        ['Email login', 'Works (non-unique email race)', 'Form never calls BFF', 'Broken e2e'],
        ['Facebook login', 'Accepts any-app tokens', '404 callback, demo client id', 'Broken'],
        ['Password reset', 'Nothing exists', 'Fake success screen', 'Fake'],
        ['Billing / pricing / quotas', 'Zero code', 'Static tiers + promises', 'Fiction'],
    ],
    [0.24, 0.36, 0.22, 0.18],
    caption='Table 7: Feature reality matrix (condensed from agent X2\'s 20-feature audit).')

# ═════════════════════ 20. QUALITY DASHBOARD ═════════════════════
story += h1_block('20', 'Quality Assessment Dashboard')
story.append(body(
    'Every agent rated its slice on a 1-10 scale with written justification. The backend '
    'averages roughly 5.5 - a competent prototype with production-shaped breadth and '
    'prototype-grade reliability. The frontend\'s functional average is roughly 3.0, pulled up '
    'only by a design system that earns 8-9 on its own. The distribution below tells the story '
    'of both repositories: strong domain engineering and design at the edges, weak wiring and '
    'reliability at the core.'))
story += chart('chart_ratings.png',
               'Figure 4: Per-module quality ratings across both repositories. The dotted line marks '
               'the 6.0 "production-credible" threshold.', max_h=290)
story += make_table(
    ['Metric', 'zemest (backend)', 'zemest-platform (frontend)'],
    [
        ['Source size', '161 Python files, 23,116 LOC (+10 Jinja templates)', '137 TS/TSX files, 15,597 LOC'],
        ['API surface', '~100 routes (79 API + 10 admin + 9 HTML + test)', '4 BFF routes (unwired)'],
        ['Data layer', '18 tables via 3 competing authorities', 'Prisma scaffold, 0 imports'],
        ['Dead code (est.)', '10-15% of app code', '40%+ of src (incl. 47/49 unused UI files)'],
        ['Tests', '452 tests, never green, no CI; ~23% vacuous', 'Zero tests'],
        ['Git history', '1 commit ("Initial commit")', '8+ commits, 3 feature commits'],
        ['Security grade', 'D- (3/10)', 'D (4/10)'],
        ['Top strength', 'Tenant isolation discipline', 'Design system'],
        ['Top weakness', 'Silent failures; unwired defenses', 'Nothing is wired to anything'],
    ],
    [0.22, 0.40, 0.38],
    caption='Table 8: Codebase health metrics, consolidated from all 20 agent reports.')

# ═════════════════════ 21. ROADMAP ═════════════════════
story += h1_block('21', 'Remediation Roadmap')
story += h2_block('21.1', 'P0 - ship blockers (weeks 1-3)')
story += make_table(
    ['#', 'Fix', 'Repo', 'Effort'],
    [
        ['1', 'Wire login/register forms to the existing BFF routes; add /api/auth/me; make middleware consume it', 'platform', 'M'],
        ['2', 'Route all data through same-origin BFF proxies forwarding the cookie as Authorization: Bearer (or add CORS to backend - pick one model)', 'both', 'M'],
        ['3', 'Fix orders-create 500 (refresh/selectinload order.items)', 'backend', 'S'],
        ['4', 'Fix address-shipping 500 (float of dict)', 'backend', 'S'],
        ['5', 'Implement the Facebook OAuth callback + real client id + backend debug_token verification', 'both', 'M'],
        ['6', 'Alembic migration for scheduled_posts, post_insights, blocked_users; retire lifespan DDL', 'backend', 'S'],
        ['7', 'Fail-fast on default secrets in production; remove demo credentials from the Jinja login page', 'backend', 'S'],
        ['8', 'Delete the Caddy open-proxy rule; plan HTTPS for the webhook origin (Meta requires it)', 'infra', 'S'],
        ['9', 'Fix the FB catalog-sync TypeError and the admin invalidate_all AttributeError', 'backend', 'S'],
        ['10', 'Point the chat playground and one dashboard page at real APIs through the BFF as the integration proof-of-pattern', 'platform', 'M'],
    ],
    [0.05, 0.62, 0.14, 0.19],
    caption='Table 9: P0 ship blockers - none require new architecture; all are wiring or small fixes.',
    align_center_cols={0, 2, 3})
story += h2_block('21.2', 'P1 - high-value improvements (weeks 3-8)')
story.append(body(
    'Replace the eleven mock dashboard pages with real data (React Query is already installed); '
    'build channel onboarding so WhatsApp and Instagram credentials become settable at all; make '
    'owner chat reachable by making owner_psid writable; auto-dispatch the order API with an '
    'idempotency guard; per-tenant Postiz sessions; fix the style-learning IntegrityError and '
    'its prompt key mismatch; default rate limits on auth and webhooks; consolidate to one '
    'dashboard and one admin panel (recommendation: finish the Next platform, harden sqladmin, '
    'retire the Jinja templates); offload webhook processing to Celery with retry and a dead '
    'letter queue while fixing dispatch-before-commit races; and stand up CI that runs the '
    'existing suite after deleting or repairing the roughly fifty vacuous tests, adding the '
    'orders-create regression first.'))
story += h2_block('21.3', 'P2 - strategic bets')
story.append(body(
    'Restore or reimplement the knowledge-tree RAG (or ship embedding RAG) and wire the dead '
    'lexical fallback as the no-LLM safety net; rebuild the Arabizi engine to stop '
    'mis-classifying digit-bearing English and corrupting phone numbers, integrating the dead '
    '200-word map; build the billing and quota system the pricing page promises, or reprice to '
    'contact-sales; revive the LLM gateway so the free-tier chain has cost ceilings; purge the '
    'Tavus assets, content, and compliance claims before any public launch; and run an Egyptian '
    'pilot with three to five design partners on the Messenger-only flow, instrumenting the '
    'funnel before investing further in WhatsApp.'))

# ═════════════════════ 22. FINAL VERDICT ═════════════════════
story += h1_block('22', 'Final Verdict')
story += callout(
    '<b>Combined system grade: D+ (4/10) - a demo, not an MVP.</b> The only customer-usable path '
    '(backend plus its own Jinja dashboard) is unauthenticated by design, and the presentable '
    'path (the platform) is a static mockup whose forms, buttons, and data are simulated. '
    'Integration - the entire point of a BFF architecture - exists as an unused contract layer. '
    'Two 500-level bugs sit on the exact endpoints a wired dashboard would hit first, and the '
    'marketing leads with the one channel that is a facade.', ACCENT_2)
story.append(body(
    'Why not lower: the backend\'s core is real and structurally sound where it matters most - '
    'tenant isolation without a single IDOR in 79 endpoints, correct Meta webhook verification, '
    'a working Messenger AI pipeline, a genuine order state machine with Decimal money math - '
    'and the frontend\'s design system is genuinely excellent. The quality of the parts is '
    '5.5 to 7 out of 10. Why not higher: no working user journey spans both repositories; three '
    'competing schema authorities break fresh installs; every security enforcement layer is '
    'disconnected; the test suite has never been green; and both repositories carry rebrand '
    'provenance that manifests as brand contamination and fictional claims.'))
story.append(body(
    'The trajectory, however, is better than the grade. The gap is wiring, not architecture: '
    'the BFF contract layer is well-shaped, endpoints exist for most dashboard needs, and the '
    'mock pages are already API-shaped. A focused six to ten weeks of P0 and P1 work could '
    'plausibly lift the Messenger-only flow to a credible closed beta. The strategic risk is '
    'not technical difficulty - it is that the organization\'s demonstrated pattern of marketing '
    'first and facades under pressure is exactly what produced this gap. The codebase will '
    'believe the product is real when the CI is green, the forms submit, and the security '
    'machinery that already exists is finally switched on.'))

story += h1_block('23', 'Appendix: Deliverables and Evidence Index')
story.append(body(
    'This report is the synthesis layer. The complete evidence base - twenty detailed agent '
    'reports totaling 856 KB, including full function inventories, per-endpoint API catalogs '
    'with parameters and response schemas, model field listings, vulnerability registers with '
    'exploitation scenarios, and per-file quality ratings - is delivered alongside this document:'))
story += make_table(
    ['File', 'Contents'],
    [
        ['Z1-architecture-bootstrap.md', 'Bootstrap trace, 35 config settings, migration lineage, 7-service deployment, dependency audit'],
        ['Z2-ai-core-1.md', '14-step agent pipeline, LLM fallback chains, 21-issue register, function inventory'],
        ['Z3-ai-core-2.md', 'Language engine algorithms, Arabizi maps, order extraction, style learner, 18 issues'],
        ['Z4-api-layer-1.md', '31 endpoints cataloged: auth, conversations, customers, orders, products, webhooks'],
        ['Z5-api-layer-2.md', '48 endpoints cataloged: crawl, dashboard, facebook, postiz, scheduling, style, tenants, address'],
        ['Z6-models-schemas.md', '18 models field-by-field, ER diagram, 28 Pydantic classes, schema-authority reconciliation'],
        ['Z7-services-1.md', '29 service functions: auth, tenant, owner chat, orders, order API, products'],
        ['Z8-services-2.md', '31 channel functions: FB, Messenger, WhatsApp, notifications, STT, vision, importers'],
        ['Z9-knowledge-engine.md', 'Crawler, indexer (PageIndex post-mortem), retriever bugs, tree sync, RAG assessment'],
        ['Z10-middleware-security.md', '7 middleware deep-dives, 25-finding vulnerability register, phone/address utils'],
        ['Z11-scheduling-admin.md', '16 publisher functions, Celery topology, 3 admin surfaces, 10 Jinja templates'],
        ['Z12-tests-docs.md', '452-test inventory, vacuous-test audit, docs-vs-reality gap, discovered production bug'],
        ['P1-app-shell.md', 'App shell, middleware line-by-line, tavus design system, Caddy/deploy config'],
        ['P2-marketing-pages.md', '26-page catalog, forms analysis, content quality, compliance-claims audit'],
        ['P3-dashboard.md', '12 dashboard pages, api-client post-mortem, 19 issues with file:line'],
        ['P4-admin-auth.md', 'Admin pages, auth architecture end-to-end, stores/hooks, 29-issue register'],
        ['P5-bff-data.md', 'BFF routes, OAuth flow, Prisma, mini-services, build scripts, auth-flow diagram'],
        ['P6-components.md', '13 site components, shadcn/ui inventory (49 files), content-claims audit'],
        ['X1-security-audit.md', '46-finding register, 3 attack walkthroughs, threat model, OWASP mapping, remediation'],
        ['X2-integration-synthesis.md', 'Integration map, 17-call contract matrix, 20-feature reality matrix, roadmap'],
    ],
    [0.30, 0.70],
    caption='Table 10: The twenty detailed analysis reports delivered with this document.')
story.append(body(
    'The repositories themselves were cloned to /home/z/my-project/repos/ for this audit and '
    'remain available for re-verification of any finding. Every claim in this report is '
    'traceable through these files to a specific file and line in the source code.'))

# ══════════════════════════ BUILD ══════════════════════════
doc = TocDocTemplate(
    OUT_BODY, pagesize=A4,
    leftMargin=MARGIN, rightMargin=MARGIN,
    topMargin=MARGIN, bottomMargin=0.95 * inch,
    title='Zemest Deep Code Analysis Report',
    author='Z.ai', creator='Z.ai',
    subject='Full-stack 20-agent audit of zemest (FastAPI) and zemest-platform (Next.js)')
doc.multiBuild(story, onFirstPage=footer, onLaterPages=footer)
print('Body PDF built:', OUT_BODY)
print('Body start page:', BODY_START[0])
