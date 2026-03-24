#!/usr/bin/env python3
"""
Build a custom TTF font from SVG currency symbols.
Maps:
  dirham_1.svg -> U+E900
  riyal.svg    -> U+E901
  dirham_2.svg -> U+E902
"""

import os
import xml.etree.ElementTree as ET
import re
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SVG_DIR = os.path.join(SCRIPT_DIR, 'svg')
FONTS_DIR = os.path.join(SCRIPT_DIR, 'fonts')


def parse_svg_paths(svg_file):
    """Extract path data and viewBox from an SVG file."""
    tree = ET.parse(svg_file)
    root = tree.getroot()

    vb = root.get('viewBox')
    if vb:
        parts = vb.replace(',', ' ').split()
        vb_x, vb_y, vb_w, vb_h = [float(p) for p in parts]
    else:
        vb_x, vb_y = 0, 0
        vb_w = float(root.get('width', 1000))
        vb_h = float(root.get('height', 1000))

    paths = []
    for elem in root.iter():
        tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
        if tag == 'path':
            d = elem.get('d')
            if d:
                paths.append(d)

    return paths, (vb_x, vb_y, vb_w, vb_h)


def parse_path_to_segments(d):
    """Parse SVG path 'd' attribute into segments with absolute coordinates."""
    tokens = re.findall(r'[A-Za-z]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?', d)

    segments = []
    i = 0
    cx, cy = 0, 0
    sx, sy = 0, 0
    last_cmd = None
    last_cp = None

    def next_num():
        nonlocal i
        val = float(tokens[i])
        i += 1
        return val

    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
        else:
            cmd = last_cmd
            if cmd == 'M':
                cmd = 'L'
            elif cmd == 'm':
                cmd = 'l'

        if cmd in ('M', 'm'):
            x, y = next_num(), next_num()
            if cmd == 'm':
                x += cx; y += cy
            cx, cy = x, y
            sx, sy = x, y
            segments.append(('moveTo', [(x, y)]))
            last_cp = None
        elif cmd in ('L', 'l'):
            x, y = next_num(), next_num()
            if cmd == 'l':
                x += cx; y += cy
            segments.append(('lineTo', [(x, y)]))
            cx, cy = x, y
            last_cp = None
        elif cmd in ('H', 'h'):
            x = next_num()
            if cmd == 'h':
                x += cx
            segments.append(('lineTo', [(x, cy)]))
            cx = x
            last_cp = None
        elif cmd in ('V', 'v'):
            y = next_num()
            if cmd == 'v':
                y += cy
            segments.append(('lineTo', [(cx, y)]))
            cy = y
            last_cp = None
        elif cmd in ('C', 'c'):
            x1, y1 = next_num(), next_num()
            x2, y2 = next_num(), next_num()
            x, y = next_num(), next_num()
            if cmd == 'c':
                x1 += cx; y1 += cy
                x2 += cx; y2 += cy
                x += cx; y += cy
            segments.append(('curveTo', [(x1, y1), (x2, y2), (x, y)]))
            last_cp = (x2, y2)
            cx, cy = x, y
        elif cmd in ('S', 's'):
            x2, y2 = next_num(), next_num()
            x, y = next_num(), next_num()
            if cmd == 's':
                x2 += cx; y2 += cy
                x += cx; y += cy
            if last_cp:
                x1 = 2 * cx - last_cp[0]
                y1 = 2 * cy - last_cp[1]
            else:
                x1, y1 = cx, cy
            segments.append(('curveTo', [(x1, y1), (x2, y2), (x, y)]))
            last_cp = (x2, y2)
            cx, cy = x, y
        elif cmd in ('Q', 'q'):
            x1, y1 = next_num(), next_num()
            x, y = next_num(), next_num()
            if cmd == 'q':
                x1 += cx; y1 += cy
                x += cx; y += cy
            # Convert quadratic to cubic for intermediate handling,
            # but TTGlyphPen uses qCurveTo
            segments.append(('qCurveTo', [(x1, y1), (x, y)]))
            last_cp = (x1, y1)
            cx, cy = x, y
        elif cmd in ('T', 't'):
            x, y = next_num(), next_num()
            if cmd == 't':
                x += cx; y += cy
            if last_cp:
                x1 = 2 * cx - last_cp[0]
                y1 = 2 * cy - last_cp[1]
            else:
                x1, y1 = cx, cy
            segments.append(('qCurveTo', [(x1, y1), (x, y)]))
            last_cp = (x1, y1)
            cx, cy = x, y
        elif cmd in ('Z', 'z'):
            segments.append(('closePath', []))
            cx, cy = sx, sy
            last_cp = None
        elif cmd in ('A', 'a'):
            rx = next_num(); ry = next_num()
            rotation = next_num()
            large_arc = next_num(); sweep = next_num()
            x, y = next_num(), next_num()
            if cmd == 'a':
                x += cx; y += cy
            segments.append(('lineTo', [(x, y)]))
            cx, cy = x, y
            last_cp = None

        last_cmd = cmd

    return segments


def cubic_to_quadratic_simple(p0, p1, p2, p3):
    """Approximate a cubic bezier with quadratic segments.
    Simple midpoint approach — for font glyphs this is usually fine."""
    # For a simple approximation, use the midpoint of the two control points
    # This works well when the cubic is close to a quadratic
    qp1_x = (3 * (p1[0] + p2[0]) - p0[0] - p3[0]) / 4
    qp1_y = (3 * (p1[1] + p2[1]) - p0[1] - p3[1]) / 4
    return (round(qp1_x), round(qp1_y)), (round(p3[0]), round(p3[1]))


def svg_to_tt_glyph(svg_file, units_per_em=1000, cap_height=700, descender=-50):
    """Parse SVG and return a TTGlyph and its advance width.

    Scales glyphs to fit within cap_height and shifts baseline so they
    align vertically with regular text/numbers.
    """
    paths, (vb_x, vb_y, vb_w, vb_h) = parse_svg_paths(svg_file)

    # Scale based on HEIGHT so all glyphs have consistent vertical size
    target_height = cap_height - descender  # e.g. 700 - (-50) = 750
    scale = target_height / vb_h
    x_offset = -vb_x
    y_offset = -vb_y

    # y_shift moves the glyph down so its bottom sits at descender level
    y_shift = descender

    pen = TTGlyphPen(None)
    last_point = (0, 0)

    for path_d in paths:
        segments = parse_path_to_segments(path_d)

        for seg_type, points in segments:
            transformed = []
            for px, py in points:
                tx = (px + x_offset) * scale
                ty = (vb_h - (py + y_offset)) * scale + y_shift
                transformed.append((round(tx), round(ty)))

            if seg_type == 'moveTo':
                pen.moveTo(transformed[0])
                last_point = transformed[0]
            elif seg_type == 'lineTo':
                pen.lineTo(transformed[0])
                last_point = transformed[0]
            elif seg_type == 'curveTo':
                # Convert cubic to quadratic
                p0 = last_point
                p1, p2, p3 = transformed
                qp1, qp3 = cubic_to_quadratic_simple(p0, p1, p2, p3)
                pen.qCurveTo(qp1, qp3)
                last_point = qp3
            elif seg_type == 'qCurveTo':
                pen.qCurveTo(*transformed)
                last_point = transformed[-1]
            elif seg_type == 'closePath':
                pen.closePath()

    glyph = pen.glyph()

    # Calculate width from the glyph bounds
    if hasattr(glyph, 'xMax') and glyph.xMax is not None:
        width = glyph.xMax + 50
    else:
        width = round(vb_w * scale) + 50

    return glyph, width


def build_font():
    UPM = 1000

    glyphs_info = {
        'dirham1': {'file': os.path.join(SVG_DIR, 'dirham_1.svg'), 'unicode': 0xE900, 'cap_height': 700, 'descender': -10},
        'riyal':   {'file': os.path.join(SVG_DIR, 'riyal.svg'),    'unicode': 0xE901, 'cap_height': 700, 'descender': 0},
        'dirham2': {'file': os.path.join(SVG_DIR, 'dirham_2.svg'), 'unicode': 0xE902, 'cap_height': 700, 'descender': -75},
    }

    glyph_names = ['.notdef'] + list(glyphs_info.keys())

    # Build .notdef glyph
    notdef_pen = TTGlyphPen(None)
    notdef_pen.moveTo((100, 0))
    notdef_pen.lineTo((100, 700))
    notdef_pen.lineTo((400, 700))
    notdef_pen.lineTo((400, 0))
    notdef_pen.closePath()
    notdef_glyph = notdef_pen.glyph()

    glyph_objects = {'.notdef': notdef_glyph}
    metrics = {'.notdef': (500, 100)}

    for name, info in glyphs_info.items():
        glyph, width = svg_to_tt_glyph(info['file'], UPM, info['cap_height'], info['descender'])
        glyph_objects[name] = glyph
        lsb = glyph.xMin if hasattr(glyph, 'xMin') and glyph.xMin is not None else 0
        metrics[name] = (width, lsb)

    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(glyph_names)

    cmap = {info['unicode']: name for name, info in glyphs_info.items()}
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyph_objects)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=800, descent=-200)

    fb.setupNameTable({
        "familyName": "CurrencySymbols",
        "styleName": "Regular",
    })

    fb.setupOS2(
        sTypoAscender=800,
        sTypoDescender=-200,
        sTypoLineGap=0,
        usWinAscent=1000,
        usWinDescent=200,
        sxHeight=500,
        sCapHeight=700,
    )

    fb.setupPost()

    # Save TTF
    os.makedirs(FONTS_DIR, exist_ok=True)
    output_ttf = os.path.join(FONTS_DIR, 'CurrencySymbols.ttf')
    fb.font.save(output_ttf)
    print(f"TTF saved to {output_ttf}")

    # Generate WOFF2
    try:
        from fontTools.ttLib import TTFont
        font = TTFont(output_ttf)
        font.flavor = 'woff2'
        woff2_path = os.path.join(FONTS_DIR, 'CurrencySymbols.woff2')
        font.save(woff2_path)
        font.close()
        print(f"WOFF2 saved to {woff2_path}")
    except Exception as e:
        print(f"WOFF2 skipped (pip3 install brotli): {e}")

    # Generate WOFF
    try:
        font = TTFont(output_ttf)
        font.flavor = 'woff'
        woff_path = os.path.join(FONTS_DIR, 'CurrencySymbols.woff')
        font.save(woff_path)
        font.close()
        print(f"WOFF saved to {woff_path}")
    except Exception as e:
        print(f"WOFF skipped: {e}")

    print("\n--- Glyph Mapping ---")
    print(f"  dirham_1.svg -> U+E900")
    print(f"  riyal.svg    -> U+E901")
    print(f"  dirham_2.svg -> U+E902")

    print("\n--- CSS ---")
    print("""@font-face {
  font-family: 'CurrencySymbols';
  src: url('./CurrencySymbols.woff2') format('woff2'),
       url('./CurrencySymbols.woff') format('woff'),
       url('./CurrencySymbols.ttf') format('truetype');
  font-weight: normal;
  font-style: normal;
}

.currency-icon {
  font-family: 'CurrencySymbols';
  font-style: normal;
  font-weight: normal;
}""")

    print("\n--- React Usage ---")
    print("""// Dirham 1: <span className="currency-icon">{'\\uE900'}</span>
// Riyal:    <span className="currency-icon">{'\\uE901'}</span>
// Dirham 2: <span className="currency-icon">{'\\uE902'}</span>

// Or constants:
const DIRHAM_1 = '\\uE900';
const RIYAL    = '\\uE901';
const DIRHAM_2 = '\\uE902';""")


if __name__ == '__main__':
    build_font()
