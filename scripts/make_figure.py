#!/usr/bin/env python3
"""
One figure, generated from the evidence file rather than drawn by hand.

Why this and not a screenshot
-----------------------------
A figure is the part of a write-up a reader trusts most and checks least, so
it is the worst place for a number to drift away from the run that produced
it. This reads `evidence/round5_shift.json` and emits SVG, so the picture
cannot disagree with the table — and `tests/` asserts the figure is no older
than its source.

Why the shift sweep and not the headline
----------------------------------------
Because it is the one result that is clearer as a shape than as digits. Two
curves diverging, and a third line that does not move at all: the method's own
confidence statement, flat, while the thing it certifies fails. A table makes
a reader compare six pairs of numbers to see that. The figure shows it at a
glance.

No plotting dependency. Hand-written SVG is about eighty lines here, against
adding matplotlib to a repository whose only runtime dependency is the
standard library — and the point of that choice is visible in `scorer.py`,
which writes out a logistic regression for the same reason.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

W, H = 880, 450
L, R, T, B = 66, 292, 56, 74
PW, PH = W - L - R, H - T - B

ALPHA = 0.20

# Chosen to hold up on GitHub's light and dark themes without a theme switch:
# a warm red and a cool teal, both mid-luminance, distinguishable in greyscale
# by the line style as well as the hue.
POOLED = "#d6453d"
GROUPED = "#0f8a84"
BOUND = "#b07d12"


def x(share: float) -> float:
    return L + share * PW


def y(rate: float) -> float:
    return T + (1.0 - rate) * PH


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main() -> int:
    src = ROOT / "evidence" / "round5_shift.json"
    if not src.exists():
        print("  evidence/round5_shift.json not built yet — "
              "run scripts/run_round5.py")
        return 1
    sweep = json.loads(src.read_text())["shift"]["sweep"]

    def series(scheme: str) -> list[tuple[float, float]]:
        pts = [p for p in sweep["points"]
               if p["scheme"] == scheme and p["alpha"] == ALPHA]
        return sorted((p["target_share"], p["violation_rate"] or 0.0)
                      for p in pts)

    pooled, grouped = series("pooled"), series("by-band")
    bound = next(p["mean_reported_bound"] for p in sweep["points"]
                 if p["scheme"] == "pooled" and p["alpha"] == ALPHA)
    natural = pooled[0][0]

    # The body is emitted first and the canvas sized to it afterwards. The
    # right-hand labels are laid out from the data, so their total height is
    # not known until they are placed -- guessing it is how the last block
    # ended up clipped off the bottom on the first attempt.
    o: list[str] = []
    add = o.append

    # Light theme is written as explicit fill/stroke ATTRIBUTES, and dark
    # theme as a CSS override on top. That ordering matters: a renderer that
    # ignores CSS -- and some do, including the one this figure was proofed
    # in -- still gets correct, readable colors rather than black everything.
    # CSS custom properties alone would have failed silently there, which is
    # the usual way an SVG looks fine in a browser and wrong everywhere else.
    add('<style>'
        '.ttl{font-size:15.5px;font-weight:600}'
        '.sub{font-size:11.5px}'
        '.ax{font-size:11px}'
        '.lbl{font-size:12px;font-weight:600}'
        '.note{font-size:10.5px}'
        '@media (prefers-color-scheme: dark){'
        '.ttl{fill:#e6edf3}'
        '.sub,.ax,.note{fill:#9198a1}'
        '.grid{stroke:#30363d}'
        '.rule{stroke:#6e7681}'
        '}'
        '</style>')

    add(f'<text class="ttl" x="{L}" y="24" fill="#1f2328">'
        'The guarantee fails silently when the applicant mix shifts</text>')
    add(f'<text class="sub" x="{L}" y="43" fill="#656d76">'
        f'Share of trials exceeding a stated {ALPHA:.0%} tolerance · 672 '
        f'cases, 300 trials per point</text>')

    # Grid and y axis.
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        yy = y(frac)
        add(f'<line class="grid" x1="{L}" y1="{yy:.1f}" x2="{L + PW}" '
            f'y2="{yy:.1f}" stroke="#d8dee4" stroke-width="1"/>')
        add(f'<text class="ax" x="{L - 10}" y="{yy + 3.5:.1f}" '
            f'fill="#656d76" text-anchor="end">{frac:.0%}</text>')

    # x axis.
    for share, _ in pooled:
        # The rightmost tick sits at the plot edge and a centred label runs
        # into the legend column beside it, so that one ends where the plot
        # does.
        anchor = "end" if share >= 1.0 else "middle"
        add(f'<text class="ax" x="{x(share):.1f}" y="{T + PH + 20}" '
            f'fill="#656d76" text-anchor="{anchor}">{share:.0%}</text>')
    add(f'<text class="ax" x="{L + PW / 2:.1f}" y="{T + PH + 42}" '
        f'fill="#656d76" text-anchor="middle">share of deployed cases drawn '
        f'from the lowest-income band</text>')

    # The natural mix, marked: everything right of it is a shift.
    add(f'<line class="rule" x1="{x(natural):.1f}" y1="{T}" '
        f'x2="{x(natural):.1f}" y2="{T + PH}" stroke="#656d76" '
        f'stroke-width="1" stroke-dasharray="2 4"/>')
    add(f'<text class="note" x="{x(natural) + 6:.1f}" y="{T + 13}" '
        f'fill="#656d76">calibrated here ({natural:.1%})</text>')

    # The certificate the method issues. Flat, which is the point.
    add(f'<line x1="{L}" y1="{y(bound):.1f}" x2="{L + PW}" '
        f'y2="{y(bound):.1f}" stroke="{BOUND}" stroke-width="2" '
        f'stroke-dasharray="7 5"/>')

    for pts, color, dash in ((pooled, POOLED, ""),
                             (grouped, GROUPED, "")):
        path = " ".join(f"{'M' if i == 0 else 'L'}{x(s):.1f},{y(v):.1f}"
                        for i, (s, v) in enumerate(pts))
        add(f'<path d="{path}" fill="none" stroke="{color}" '
            f'stroke-width="2.6" stroke-linejoin="round"{dash}/>')
        for s, v in pts:
            add(f'<circle cx="{x(s):.1f}" cy="{y(v):.1f}" r="3.6" '
                f'fill="{color}"/>')

    # Labels where each curve ends, rather than a legend box the reader has
    # to map back onto the lines. Each block is placed from its own series'
    # final y, then nudged so the three never overlap.
    lx = L + PW + 16

    # Each block wants to sit beside the thing it names. Three of them in a
    # 320px column collide, so they are laid out top-down with a minimum gap
    # and pushed apart where they would overlap -- deterministic, and
    # readable whatever the data does, which hand-placed offsets are not:
    # the first attempt put the bound and the grouped curve 8px apart and
    # rendered them on top of each other.
    LINE, GAP = 14.0, 12.0

    wanted = [
        (y(pooled[-1][1]) + 4, POOLED, "one global threshold",
         [f'<tspan font-weight="600">{pooled[0][1]:.1%}</tspan> of trials '
          f'violate at the mix',
          f'it was calibrated on, <tspan font-weight="600">'
          f'{pooled[-1][1]:.0%}</tspan> at the far end']),
        (y(bound) - 6, BOUND, "the bound it reported",
         [f'<tspan font-weight="600">{bound:.3f}</tspan> at every point. It is '
          f'computed',
          'on calibration data, which never',
          'shifted, so an operator watching',
          'it sees nothing wrong.']),
        (y(grouped[-1][1]) + 4, GROUPED, "one threshold per band",
         [f'never leaves <tspan font-weight="600">{grouped[-1][1]:.1%}</tspan>'
          f'. Re-weighting groups',
          'calibrated separately changes',
          'which thresholds are used, not',
          'what any one of them is.']),
    ]

    cursor = T
    for want, color, head, lines in wanted:
        top = max(want, cursor)
        add(f'<text class="lbl" x="{lx}" y="{top:.1f}" fill="{color}">'
            f'{esc(head)}</text>')
        for i, line in enumerate(lines):
            add(f'<text class="note" x="{lx}" y="{top + 16 + i * LINE:.1f}" '
                f'fill="#656d76">{line}</text>')
        cursor = top + 16 + len(lines) * LINE + GAP

    height = max(H, cursor + 6)
    add(f'<text class="note" x="{L}" y="{height - 10}" fill="#656d76">'
        f'{esc("evidence/round5_shift.json · scripts/make_figure.py")}'
        f'</text>')
    add("</svg>")

    o.insert(0,
             f'<svg xmlns="http://www.w3.org/2000/svg" '
             f'viewBox="0 0 {W} {height:.0f}" width="{W}" '
             f'height="{height:.0f}" font-family="-apple-system, '
             f'BlinkMacSystemFont, \'Segoe UI\', Helvetica, Arial, '
             f'sans-serif" role="img" aria-label="As the applicant mix '
             f'shifts toward the lowest-income band, a single global '
             f'threshold goes from {pooled[0][1]:.1%} to '
             f'{pooled[-1][1]:.0%} of trials violating, while the bound it '
             f'reports stays at {bound:.3f} throughout. One threshold per '
             f'band never leaves {grouped[-1][1]:.1%}.">')

    dest = ROOT / "docs" / "shift.svg"
    dest.write_text("\n".join(o) + "\n")
    print(f"  wrote {dest.relative_to(ROOT)} "
          f"({dest.stat().st_size:,} bytes)")
    print(f"  pooled {pooled[0][1]:.1%} -> {pooled[-1][1]:.1%}, "
          f"grouped {grouped[0][1]:.1%} -> {grouped[-1][1]:.1%}, "
          f"bound flat at {bound:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
