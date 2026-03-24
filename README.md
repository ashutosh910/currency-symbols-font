# CurrencySymbols Font

Custom icon font for the new **UAE Dirham** and **Saudi Riyal** currency symbols that don't yet have official Unicode codepoints.

## Glyph Mapping

| Symbol              | SVG Source     | Unicode (PUA) | HTML Entity  | JS Escape  |
|---------------------|----------------|---------------|--------------|------------|
| Dirham              | `dirham_1.svg` | U+E900        | `&#xE900;`   | `\uE900`   |
| Riyal               | `riyal.svg`    | U+E901        | `&#xE901;`   | `\uE901`   |
| Dirham (sans-serif) | `dirham_2.svg` | U+E902        | `&#xE902;`   | `\uE902`   |

All codepoints are in the Unicode [Private Use Area (PUA)](https://en.wikipedia.org/wiki/Private_Use_Areas) so they won't conflict with standard characters.

## Project Structure

```
currency/
├── svg/                        # Source SVG files
│   ├── dirham_1.svg
│   ├── dirham_2.svg
│   └── riyal.svg
├── fonts/                      # Generated font files
│   ├── CurrencySymbols.ttf
│   ├── CurrencySymbols.woff
│   └── CurrencySymbols.woff2
├── build_font.py               # Font build script
├── test_font.html              # Visual alignment test page
├── requirements.txt            # Python dependencies
└── README.md
```

## Prerequisites

- Python 3.8+
- pip

## Setup

```bash
pip install -r requirements.txt
```

This installs:
- `fonttools` — font building and manipulation
- `brotli` — WOFF2 compression

## Building the Font

```bash
python3 build_font.py
```

This reads SVGs from `svg/` and outputs TTF, WOFF, and WOFF2 files to `fonts/`.

## Adding or Replacing SVGs

1. Place your SVG file in the `svg/` directory
2. Edit the `glyphs_info` dict in `build_font.py` (~line 242):

```python
glyphs_info = {
    'dirham1': {'file': os.path.join(SVG_DIR, 'dirham_1.svg'), 'unicode': 0xE900, 'cap_height': 700, 'descender': -10},
    'riyal':   {'file': os.path.join(SVG_DIR, 'riyal.svg'),    'unicode': 0xE901, 'cap_height': 700, 'descender': 0},
    'dirham2': {'file': os.path.join(SVG_DIR, 'dirham_2.svg'), 'unicode': 0xE902, 'cap_height': 700, 'descender': -75},
}
```

3. Re-run `python3 build_font.py`

### Tuning Vertical Alignment

Each glyph has two parameters that control its vertical position relative to text:

| Parameter    | Default | Effect                                                                 |
|-------------|---------|------------------------------------------------------------------------|
| `cap_height` | `700`   | Top of the glyph. Increase = taller/higher, decrease = shorter/lower   |
| `descender`  | varies  | Bottom of the glyph. More negative = shifts down, closer to 0 = shifts up |

To test alignment visually, open `test_font.html` in a browser (with a local server):

```bash
python3 -m http.server 8765
# Open http://localhost:8765/test_font.html
```

The test page shows red (top), green (center), and blue (bottom) guide lines for each glyph next to "100".

## Usage in React

### 1. Add the font files

Copy the `fonts/` directory into your project (e.g. `src/assets/fonts/`).

### 2. Declare the @font-face

```css
@font-face {
  font-family: 'CurrencySymbols';
  src: url('./fonts/CurrencySymbols.woff2') format('woff2'),
       url('./fonts/CurrencySymbols.woff') format('woff'),
       url('./fonts/CurrencySymbols.ttf') format('truetype');
  font-weight: normal;
  font-style: normal;
}
```

### 3. Use in components

```jsx
// Define constants
const DIRHAM_1 = '\uE900';
const RIYAL    = '\uE901';
const DIRHAM_2 = '\uE902';

// Use inline
<span style={{ fontFamily: 'CurrencySymbols' }}>{DIRHAM_1}</span>

// Or with a CSS class
<span className="currency-icon">{RIYAL}</span>

// Or with HTML entities
<span className="currency-icon" dangerouslySetInnerHTML={{ __html: '&#xE900;' }} />
```

## Usage in plain HTML

```html
<span style="font-family: CurrencySymbols">&#xE900;</span>
<span style="font-family: CurrencySymbols">&#xE901;</span>
<span style="font-family: CurrencySymbols">&#xE902;</span>
```
