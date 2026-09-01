#!/usr/bin/env python3
"""Generate charts for the Zemest Deep Code Analysis Report."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.font_manager as fm
fm.fontManager.addfont('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')

import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

OUT = '/home/z/my-project/scripts/assets'
import os
os.makedirs(OUT, exist_ok=True)

# ── Palette (from palette.cascade, seed 42) ──
ACCENT   = '#1f6c92'
ACCENT_2 = '#c23a50'
HEADER   = '#32454e'
ICON     = '#4b86a4'
BORDER   = '#acbdc5'
MUTED    = '#747b7e'
SEM_ERR  = '#a25b54'
SEM_WARN = '#8c7443'
SEM_INFO = '#507aa4'
SEM_OK   = '#529067'
TXT      = '#131515'

# ═══════════════ CHART 1: Module quality ratings (horizontal bars) ═══════════════
backend = [
    ('Documentation', 4.0), ('Test suite', 4.5), ('Knowledge engine (RAG)', 4.5),
    ('Middleware & security', 5.0), ('Architecture & bootstrap', 5.5),
    ('AI engine core', 5.5), ('Scheduling / tasks / admin', 5.5),
    ('API layer', 5.8), ('Business services', 6.0), ('Data models', 6.0),
    ('Pydantic schemas', 6.5),
]
frontend = [
    ('Dashboard pages', 3.0), ('Admin & auth pages', 3.0), ('Marketing site', 3.5),
    ('BFF & data layer', 4.0), ('Site components', 6.0), ('App shell & design system', 7.0),
]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.6, 4.6), constrained_layout=True,
                                gridspec_kw={'width_ratios': [1.25, 1]})
for ax, data, color, title in ((ax1, backend, ACCENT, 'Backend (zemest)'),
                                (ax2, frontend, ICON, 'Frontend (zemest-platform)')):
    names = [d[0] for d in data][::-1]
    vals = [d[1] for d in data][::-1]
    bars = ax.barh(names, vals, color=color, height=0.62, edgecolor='none', zorder=3)
    for b, v in zip(bars, vals):
        ax.text(v + 0.12, b.get_y() + b.get_height() / 2, f'{v:.1f}',
                va='center', ha='left', fontsize=8.5, color=TXT)
    ax.set_xlim(0, 10.6)
    ax.set_title(title, fontsize=10.5, fontweight='bold', loc='left', color=TXT, pad=8)
    ax.tick_params(axis='y', labelsize=8.6, colors=TXT, length=0)
    ax.tick_params(axis='x', labelsize=8, colors=MUTED)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_color(BORDER)
    ax.grid(axis='x', linestyle='--', alpha=0.2, linewidth=0.5, zorder=0)
    ax.axvline(6.0, color=MUTED, linestyle=':', linewidth=0.8, alpha=0.5)
fig.savefig(f'{OUT}/chart_ratings.png', dpi=200, facecolor='white')
plt.close(fig)

# ═══════════════ CHART 2: Feature reality verdicts ═══════════════
verdicts = [
    ('Works', 1, SEM_OK),
    ('Partially works', 8, ICON),
    ('Broken / dead / facade', 10, SEM_ERR),
    ('Aspirational (no code)', 1, SEM_WARN),
]
fig, ax = plt.subplots(figsize=(9.2, 2.6), constrained_layout=True)
names = [v[0] for v in verdicts][::-1]
vals = [v[1] for v in verdicts][::-1]
cols = [v[2] for v in verdicts][::-1]
bars = ax.barh(names, vals, color=cols, height=0.58, edgecolor='none', zorder=3)
for b, v in zip(bars, vals):
    ax.text(v + 0.15, b.get_y() + b.get_height() / 2, str(v),
            va='center', ha='left', fontsize=10, fontweight='bold', color=TXT)
ax.set_xlim(0, 11.5)
ax.set_xlabel('Features (of 20 audited)', fontsize=9, color=MUTED)
ax.tick_params(axis='y', labelsize=9.5, colors=TXT, length=0)
ax.tick_params(axis='x', labelsize=8, colors=MUTED)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_visible(False)
ax.spines['bottom'].set_color(BORDER)
ax.grid(axis='x', linestyle='--', alpha=0.2, linewidth=0.5, zorder=0)
fig.savefig(f'{OUT}/chart_features.png', dpi=200, facecolor='white')
plt.close(fig)

# ═══════════════ CHART 3: Vulnerability severity (donut) ═══════════════
sev = [('Critical', 10, SEM_ERR), ('High', 14, ACCENT_2),
       ('Medium', 16, SEM_WARN), ('Low', 6, SEM_INFO)]
fig, ax = plt.subplots(figsize=(7.4, 3.4), constrained_layout=True)
vals = [s[1] for s in sev]
cols = [s[2] for s in sev]
wedges, _ = ax.pie(vals, colors=cols, startangle=90, counterclock=False,
                   wedgeprops=dict(width=0.34, edgecolor='white', linewidth=1.5))
ax.text(0, 0.06, '46', ha='center', va='center', fontsize=22, fontweight='bold', color=TXT)
ax.text(0, -0.24, 'findings', ha='center', va='center', fontsize=9, color=MUTED)
# Rich legend on the right (Strategy C - no labels on chart)
legend_labels = [f'{s[0]}  —  {s[1]}  ({s[1]/46*100:.0f}%)' for s in sev]
ax.legend(wedges, legend_labels, loc='center left', bbox_to_anchor=(1.02, 0.5),
          frameon=False, fontsize=9.5, handlelength=1.0, handleheight=1.0,
          labelcolor=TXT, borderaxespad=0)
ax.set_aspect('equal')
fig.savefig(f'{OUT}/chart_vulns.png', dpi=200, facecolor='white')
plt.close(fig)

print('Charts generated OK:')
for f in sorted(os.listdir(OUT)):
    print(' -', f, os.path.getsize(os.path.join(OUT, f)), 'bytes')
