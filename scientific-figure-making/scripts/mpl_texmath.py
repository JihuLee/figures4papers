#!/usr/bin/env python3
"""mpl_texmath.py - real LaTeX math inside matplotlib figures, with the sans text left alone.

Every $...$ segment of a label becomes its own usetex text object; the rest of the label stays in the figure's font.
The segments are measured and placed on one common baseline. text.usetex is never switched on globally.

    import mpl_texmath as tm
    tm.setup_math(paper="paper/main.tex")          # math font, packages and \newcommand macros of the paper
    tm.mixed_text(ax, 0.5, 0.5, r"scores $S[i,v,p]$", fontsize=6, ha="center", transform=ax.transAxes)
    tm.mixed_legend(ax.legend())                   # legend entries with $...$
    tm.save_figure(fig, "figures/fig1")            # PDF (+PNG without dvipng) and a font/size check

Sizes: a math segment is compiled at the text's size, so LaTeX picks its design sizes (cmmi6 at 6pt) and script
sizes (\DeclareMathSizes: 6pt -> 5pt); non-standard sizes are declared with 0.7/0.5 ratios and a 5pt floor.
check_pdf() rejects Type 3 fonts and text below 5pt (scripts included) and warns below 6pt.

The preamble code is shared with ml-paper-figure's tex_math.py; keep the two in sync.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import warnings
from pathlib import Path

# LaTeX defaults (fontmath.ltx): text size -> (script, scriptscript)
LATEX_MATH_SIZES = {5: (5, 5), 6: (5, 5), 7: (5, 5), 8: (6, 5), 9: (6, 5), 10: (7, 5), 10.95: (8, 6), 12: (9, 7),
                    14.4: (10.95, 8), 17.28: (12, 10), 20.74: (14.4, 12), 24.88: (20.74, 17.28)}
MIN_SCRIPT_PT = 5.0

# Math font setups. Keys are accepted by --math; anything containing a backslash is used verbatim.
MATH_SETUPS = {
    "cm": "",                                    # Computer Modern (LaTeX default; cvpr/iccv/neurips/icml/iclr bodies)
    "lmodern": r"\usepackage{lmodern}",
    "newtx": r"\usepackage{newtxmath}",          # Times-like math (acl, many IEEE/Springer setups)
    "newtx-libertine": r"\usepackage[libertine]{newtxmath}",
    "mathptmx": r"\usepackage{mathptmx}",
    "newpx": r"\usepackage{newpxmath}",          # Palatino-like
    "mathpazo": r"\usepackage{mathpazo}",
    "libertinust1": r"\usepackage{libertinust1math}",
    "stix2": r"\usepackage{stix2}",
    "fourier": r"\usepackage{fourier}",
    "kpfonts": r"\usepackage{kpfonts}",
    "euler": r"\usepackage{eulervm}",
}
# packages whose presence (in the paper preamble or its local .sty/.cls) selects the math setup, in priority order
MATH_PACKAGE_RULES = [
    ("newtxmath", "newtx"), ("mathptmx", "mathptmx"), ("newpxmath", "newpx"), ("mathpazo", "mathpazo"),
    ("libertinust1math", "libertinust1"), ("stix2", "stix2"), ("fourier", "fourier"), ("kpfonts", "kpfonts"),
    ("eulervm", "euler"), ("lmodern", "lmodern"),
]
# math-related packages copied from the paper so its macros work (the text-font packages are not copied: only math
# goes through LaTeX; \usepackage{times} changes the text font only, the math stays Computer Modern)
MATH_HELPER_PACKAGES = {"amsmath", "amssymb", "amsfonts", "mathtools", "bm", "bbm", "dsfont", "mathrsfs", "upgreek",
                        "esint", "nicefrac", "xfrac", "siunitx", "physics", "cancel", "stmaryrd", "mathbbol",
                        "bbold", "accents", "units", "xspace", "amsthm", "commath", "braket", "eucal", "calrsfs"}
_DEF_CMDS = ("newcommand", "renewcommand", "providecommand", "DeclareMathOperator", "DeclareRobustCommand",
             "def", "newcommand*", "renewcommand*", "providecommand*", "DeclareMathOperator*", "DeclarePairedDelimiter",
             "DeclareMathAlphabet", "SetMathAlphabet", "DeclareSymbolFont", "DeclareMathSymbol", "DeclareMathSizes")


class TexError(RuntimeError):
    pass



# ----------------------------------------------------------------------------- paper preamble


def _strip_comments(s):
    return re.sub(r"(?<!\\)%.*", "", s)


def _balanced(s, i):
    """s[i] == '{' -> index just past the matching '}' (or -1)."""
    depth = 0
    for j in range(i, len(s)):
        c = s[j]
        if c == "\\":
            continue
        if c == "{" and (j == 0 or s[j - 1] != "\\"):
            depth += 1
        elif c == "}" and (j == 0 or s[j - 1] != "\\"):
            depth -= 1
            if depth == 0:
                return j + 1
    return -1


def _extract_definitions(src):
    r"""Macro definitions (\newcommand, \DeclareMathOperator, \def, ...) with balanced arguments."""
    out = []
    pat = re.compile(r"\\(" + "|".join(re.escape(c) for c in sorted(_DEF_CMDS, key=len, reverse=True)) + r")(?![A-Za-z])")
    pos = 0
    while True:
        m = pat.search(src, pos)
        if not m:
            break
        cmd, i = m.group(1), m.end()
        start = m.start()
        if cmd == "def":
            m2 = re.match(r"\s*(\\[A-Za-z@]+|\\.)([^{]*)", src[i:])
            if not m2:
                pos = i
                continue
            j = i + m2.end()
            if j < len(src) and src[j] == "{":
                k = _balanced(src, j)
                if k > 0:
                    out.append(src[start:k])
                    pos = k
                    continue
            pos = i
            continue
        j, args, ok = i, 0, True
        need = {"DeclareMathSizes": 4, "DeclareMathSymbol": 4, "DeclareSymbolFont": 5, "DeclareMathAlphabet": 5,
                "SetMathAlphabet": 6, "DeclarePairedDelimiter": 3}.get(cmd.rstrip("*"), 2)
        while args < need:
            while j < len(src) and src[j] in " \t\n":
                j += 1
            if j < len(src) and src[j] == "*" and args == 0:
                j += 1
                continue
            if j < len(src) and src[j] == "[":
                k = src.find("]", j)
                if k < 0:
                    ok = False
                    break
                j = k + 1
                continue
            if j < len(src) and src[j] == "{":
                k = _balanced(src, j)
                if k < 0:
                    ok = False
                    break
                j, args = k, args + 1
                continue
            if j < len(src) and src[j] == "\\" and args == 0:     # \newcommand\foo{...}
                m3 = re.match(r"\\[A-Za-z@]+|\\.", src[j:])
                j, args = j + m3.end(), 1
                continue
            ok = args >= 2 or (args >= 1 and cmd.startswith("Declare"))
            break
        if ok and args >= 1:
            out.append(src[start:j])
        pos = max(j, i)
    return out


def _safe_definition(d):
    r"""Make \newcommand / \renewcommand work whether or not the macro already exists in the snippet document."""
    m = re.match(r"\\(new|renew|provide)command(\*?)\s*(\{\s*(\\[A-Za-z@]+)\s*\}|(\\[A-Za-z@]+))", d)
    if m:
        name = m.group(4) or m.group(5)
        rest = d[m.end():]
        return f"\\providecommand{{{name}}}{{}}\\renewcommand{m.group(2)}{{{name}}}{rest}"
    m = re.match(r"\\DeclareRobustCommand(\*?)\s*(\{\s*(\\[A-Za-z@]+)\s*\}|(\\[A-Za-z@]+))", d)
    if m:
        name = m.group(3) or m.group(4)
        return f"\\providecommand{{{name}}}{{}}\\let{name}\\relax" + d
    return d


def _read(p):
    try:
        return Path(p).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def paper_preamble(paper=None, math=None, macros=True):
    """Build the snippet preamble from the paper source.

    paper : main .tex (its preamble, \\input/\\include'd macro files and local .sty/.cls files are read)
    math  : None (detect), a key of MATH_SETUPS, or verbatim LaTeX (contains a backslash)
    macros: copy the paper's \\newcommand/\\DeclareMathOperator/... definitions so figure notation equals body notation
    Returns (preamble, info).
    """
    info = {"paper": str(paper) if paper else None, "sources": [], "math": None, "macros": 0, "packages": []}
    texts = []
    if paper:
        p = Path(paper).resolve()
        if not p.exists():
            raise TexError(f"paper file {p} not found")
        main = _strip_comments(_read(p))
        cut = main.find(r"\begin{document}")
        pre = main[:cut] if cut >= 0 else main
        texts.append(pre)
        info["sources"].append(p.name)
        seen = {p}
        queue = [(p.parent, pre)]
        while queue:
            base, txt = queue.pop()
            names = []
            for m in re.finditer(r"\\(?:input|include)\s*\{([^}]+)\}", txt):
                names.append((m.group(1).strip(), (".tex", "")))
            for m in re.finditer(r"\\(?:usepackage|RequirePackage)\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}", txt):
                for n in m.group(1).split(","):
                    names.append((n.strip(), (".sty",)))
            for m in re.finditer(r"\\documentclass\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}", txt):
                names.append((m.group(1).strip(), (".cls",)))
            for n, exts in names:
                for ext in exts:
                    q = (base / (n if (not ext or n.endswith(ext)) else n + ext)).resolve()
                    if q.is_file() and q not in seen:
                        seen.add(q)
                        t = _strip_comments(_read(q))
                        texts.append(t)
                        info["sources"].append(q.name)
                        queue.append((q.parent, t))
                        break
    alltext = "\n".join(texts)
    pkgs = []
    for m in re.finditer(r"\\(?:usepackage|RequirePackage)\s*(\[[^\]]*\])?\s*\{([^}]+)\}", alltext):
        for n in m.group(2).split(","):
            pkgs.append((n.strip(), m.group(1) or ""))
    names = [n for n, _ in pkgs]
    if math is None:
        key = "cm"
        for pkg, k in MATH_PACKAGE_RULES:
            if pkg in names:
                key = k
                break
        if key in ("newtx", "newtx-libertine"):
            opt = next((o for n, o in pkgs if n == "newtxmath"), "")
            math_line = f"\\usepackage{opt}{{newtxmath}}"
        else:
            math_line = MATH_SETUPS[key]
        info["math"] = key + (" (detected)" if paper else " (default)")
    elif "\\" in math:
        math_line, info["math"] = math, "custom"
    else:
        if math not in MATH_SETUPS:
            raise TexError(f"unknown math setup '{math}'. Use one of {', '.join(MATH_SETUPS)} or verbatim LaTeX")
        math_line, info["math"] = MATH_SETUPS[math], math + " (override)"
    lines = []
    helpers = []
    for n, o in pkgs:
        if n in MATH_HELPER_PACKAGES and n not in helpers:
            helpers.append(n)
            lines.append(f"\\usepackage{o}{{{n}}}")
    # amsmath (\text, \operatorname, ...) is always available; amssymb too unless the math font package brings
    # its own symbols. Both go before the math font package, as newtxmath and friends require.
    if "amsmath" not in helpers:
        lines.insert(0, r"\usepackage{amsmath}")
    if "amssymb" not in helpers and math_line in ("", MATH_SETUPS["lmodern"]):
        lines.insert(1, r"\usepackage{amssymb}")
    if math_line:
        lines.append(math_line)
    info["packages"] = helpers
    if macros and alltext:
        defs = [_safe_definition(d) for d in _extract_definitions(alltext)]
        lines += defs
        info["macros"] = len(defs)
    return "\n".join(lines), info


# ----------------------------------------------------------------------------- sizes


def math_sizes(pt):
    """(script, scriptscript) LaTeX uses for text size pt; non-standard sizes follow 0.7/0.5 with a 5pt floor."""
    for k, v in LATEX_MATH_SIZES.items():
        if abs(k - pt) < 0.005:
            return v
    return (max(MIN_SCRIPT_PT, round(0.7 * pt, 2)), max(MIN_SCRIPT_PT, round(0.5 * pt, 2)))


def _declared_sizes(preamble):
    out = {}
    for m in re.finditer(r"\\DeclareMathSizes\s*\{([\d.]+)\}\s*\{([\d.]+)\}\s*\{([\d.]+)\}\s*\{([\d.]+)\}", preamble):
        out[round(float(m.group(1)), 2)] = (float(m.group(3)), float(m.group(4)))
    return out


def effective_sizes(pt, preamble):
    d = _declared_sizes(preamble)
    return d.get(round(pt, 2)) or math_sizes(pt)


# ----------------------------------------------------------------------------- segments


def split_math(s):
    r"""'scores $S[i,v,p]$' -> [('scores ', False), ('S[i,v,p]', True)]. \$ is a literal dollar sign."""
    out, buf, i, inmath = [], "", 0, False
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s) and s[i + 1] == "$":
            buf += "\\$" if inmath else "$"
            i += 2
            continue
        if c == "$":
            if buf or inmath:
                out.append((buf, inmath))
            buf, inmath = "", not inmath
            i += 1
            continue
        buf += c
        i += 1
    if inmath:
        raise TexError(f"unbalanced $ in {s!r}")
    if buf:
        out.append((buf, False))
    return [(t, m) for t, m in out if t or m]


def has_math(s):
    try:
        return any(m for _, m in split_math(s))
    except TexError:
        return True



# ----------------------------------------------------------------------------- environment


def tex_tools():
    """Installed TeX tools (None when missing) and whether PyMuPDF is importable."""
    out = {k: shutil.which(k) for k in ("latex", "dvipng", "dvisvgm", "kpsewhich", "pdftoppm")}
    try:
        import pymupdf  # noqa: F401
        out["pymupdf"] = True
    except Exception:
        out["pymupdf"] = False
    return out


_STATE = {"preamble": None, "info": None, "warned": set()}


def _warn_once(key, msg):
    if key not in _STATE["warned"]:
        _STATE["warned"].add(key)
        warnings.warn(msg, stacklevel=3)


def _plt():
    import matplotlib.pyplot as plt
    return plt


def setup_math(paper=None, math=None, macros=True, extra=""):
    r"""Configure the LaTeX used for $...$ segments (and only for them).

    paper : the paper's main .tex; its preamble, \input macro files and local .sty/.cls are read
    math  : None (detect from the paper; Computer Modern otherwise), 'cm', 'newtx', 'mathptmx', ... or verbatim LaTeX
    macros: copy \newcommand / \DeclareMathOperator / ... so figure notation equals body notation
    Sets rcParams['text.latex.preamble'] (read only by usetex text) and pdf.fonttype = 42. Returns an info dict.
    """
    import matplotlib as mpl
    pre, info = paper_preamble(paper, math, macros)
    if extra:
        pre += "\n" + extra
    _STATE["preamble"], _STATE["info"] = pre, info
    mpl.rcParams["text.latex.preamble"] = pre
    mpl.rcParams["text.usetex"] = False
    mpl.rcParams["pdf.fonttype"] = 42
    mpl.rcParams["ps.fonttype"] = 42
    fam = [f.lower() for f in mpl.rcParams["font.family"]]
    if len(fam) == 1 and fam[0] in ("times", "palatino") and info["math"].split()[0] not in ("mathptmx", "mathpazo"):
        warnings.warn(f"font.family '{fam[0]}' makes matplotlib load a math font package for usetex text, which would "
                      f"override the paper's math ({info['math']}); use a font name that is not one of matplotlib's "
                      "usetex families", stacklevel=2)
    if not shutil.which("latex"):
        warnings.warn("latex not found: $...$ segments fall back to matplotlib mathtext in Computer Modern "
                      "(no real LaTeX script sizes or paper macros). Install TeX Live, MiKTeX or TinyTeX.", stacklevel=2)
    return info


def _ensure_preamble():
    if _STATE["preamble"] is None:
        setup_math()
    return _STATE["preamble"]


def _ensure_math_size(pt):
    """Declare LaTeX math sizes for a non-standard text size (6.5pt -> scripts 5pt instead of LaTeX's 4.55pt)."""
    import matplotlib as mpl
    pre = mpl.rcParams["text.latex.preamble"]
    pt = round(float(pt), 3)
    if any(abs(k - pt) < 0.005 for k in LATEX_MATH_SIZES) or pt in _declared_sizes(pre):
        return
    sc, ssc = math_sizes(pt)
    f = lambda v: f"{v:.3f}".rstrip("0").rstrip(".")
    mpl.rcParams["text.latex.preamble"] = pre + f"\n\\DeclareMathSizes{{{f(pt)}}}{{{f(pt)}}}{{{f(sc)}}}{{{f(ssc)}}}"


def add_tex_font(name="texgyreheros", family=None):
    """Register an OpenType font from the TeX tree with matplotlib (e.g. TeX Gyre Heros, a Helvetica clone).

    Returns the family name to use in rcParams['font.family'], or None if kpsewhich cannot find the files."""
    import matplotlib.font_manager as fm
    if not shutil.which("kpsewhich"):
        return None
    found = None
    for style in ("regular", "bold", "italic", "bolditalic", "oblique", "boldoblique"):
        try:
            p = subprocess.run(["kpsewhich", f"{name}-{style}.otf"], capture_output=True, text=True, timeout=20).stdout.strip()
        except Exception:
            p = ""
        if p:
            fm.fontManager.addfont(p)
            found = found or fm.FontProperties(fname=p).get_name()
    return family or found


# ----------------------------------------------------------------------------- mixed text


def _pieces(s):
    """Label -> [(text, is_math)]; sans edge spaces are returned separately as (' ', False)."""
    out = []
    for t, m in split_math(s):
        if m:
            out.append((t, True))
            continue
        lead, core, trail = re.match(r"^(\s*)(.*?)(\s*)$", t, re.S).groups()
        if lead:
            out.append((" ", False))
        if core:
            out.append((core, False))
        if trail:
            out.append((" ", False))
    return out


def _text_kw(kw, fontsize, color, is_math, math_seg):
    k = dict(kw)
    k.update(fontsize=fontsize, ha="left", va="baseline", rotation_mode="anchor")
    if color is not None:
        k["color"] = color
    if is_math:
        if shutil.which("latex"):
            k["usetex"] = True
            txt = f"${math_seg}$"
        else:
            _warn_once("nolatex", "latex not found: math drawn with mathtext (Computer Modern), not LaTeX")
            k["usetex"] = False
            k["math_fontfamily"] = "cm"
            txt = f"${math_seg}$"
        for drop in ("fontfamily", "family", "fontweight", "weight", "fontstyle", "style", "fontproperties", "font"):
            k.pop(drop, None)
        return txt, k
    k["usetex"] = False
    return math_seg, k


_MEASURE_DPI = 1440.0


def _measure_renderer():
    """A high-resolution Agg renderer: text widths at the figure dpi are rounded to whole pixels."""
    from matplotlib.backends.backend_agg import RendererAgg
    r = _STATE.get("renderer")
    if r is None:
        r = _STATE["renderer"] = RendererAgg(8, 8, _MEASURE_DPI)
    return r


def _measure(fig, renderer, txt, kw):
    """(advance, y0, y1) in points of a text anchored at its baseline-left corner (TeX box metrics for usetex)."""
    import matplotlib.text as mtext
    t = mtext.Text(0, 0, txt, **{k: v for k, v in kw.items() if k not in ("ha", "va", "rotation_mode")})
    prop = t.get_fontproperties()
    ismath = "TeX" if t.get_usetex() else t._preprocess_math(txt)[1]
    s_ = t._preprocess_math(txt)[0] if not t.get_usetex() else txt
    r = _measure_renderer()
    w, h, d = r.get_text_width_height_descent(s_, prop, ismath=ismath)
    k = 72.0 / _MEASURE_DPI
    return w * k, -d * k, (h - d) * k


def _space_width(fig, renderer, kw):
    a = _measure(fig, renderer, "x x", kw)[0]
    b = _measure(fig, renderer, "xx", kw)[0]
    return max(0.0, a - b)


def _layout(fig, s, fontsize, color, kw):
    """Measure a single line -> (items [(text, kw, x_offset_pt)], width, y0, y1)."""
    renderer = None
    items, x, y0, y1 = [], 0.0, 0.0, 0.0
    for seg, is_math in _pieces(s):
        if seg == " " and not is_math:
            x += _space_width(fig, renderer, _text_kw(kw, fontsize, color, False, "")[1])
            continue
        txt, k = _text_kw(kw, fontsize, color, is_math, seg)
        if is_math and k.get("usetex"):
            _ensure_math_size(fontsize)
        w, a, b = _measure(fig, renderer, txt, k)
        items.append((txt, k, x))
        x += w
        y0, y1 = min(y0, a), max(y1, b)
    return items, x, y0, y1


def mixed_text(ax, x, y, s, fontsize=None, ha="left", va="baseline", color=None, transform=None, rotation=0.0,
               offset=(0.0, 0.0), linespacing=1.25, multialignment=None, **kw):
    r"""Draw a label whose $...$ segments are typeset by LaTeX and whose other text stays in the figure font.

    x, y      anchor in `transform` coordinates (default ax.transData; ax.transAxes, fig.transFigure, blended ...)
    ha / va   'left' | 'center' | 'right' and 'baseline' | 'center' | 'top' | 'bottom' for the whole block
    offset    extra (dx, dy) shift in points, applied in the rotated frame
    rotation  degrees; segments stay on one rotated baseline
    Lines are separated by '\n'. Returns the list of Text artists.
    """
    import math
    import matplotlib as mpl
    from matplotlib.transforms import ScaledTranslation
    _ensure_preamble()
    fig = ax.figure
    fontsize = mpl.rcParams["font.size"] if fontsize is None else fontsize
    try:
        fontsize = float(fontsize)
    except (TypeError, ValueError):
        from matplotlib.font_manager import FontProperties
        fontsize = FontProperties(size=fontsize).get_size_in_points()
    trans = ax.transData if transform is None else transform
    lines = s.split("\n")
    lays = [_layout(fig, ln, fontsize, color, kw) for ln in lines]
    lh = linespacing * fontsize
    ma = multialignment or ha
    block_w = max((L[1] for L in lays), default=0.0)
    # vertical extent of the block relative to the first baseline
    top = lays[0][3] if lays else 0.0
    bot = (lays[-1][2] - lh * (len(lays) - 1)) if lays else 0.0
    dy0 = {"baseline": 0.0, "center": -(top + bot) / 2, "top": -top, "bottom": -bot}.get(va, 0.0)
    dx0 = {"left": 0.0, "center": -block_w / 2, "right": -block_w}.get(ha, 0.0)
    th = math.radians(rotation)
    c, sn = math.cos(th), math.sin(th)
    arts = []
    for li, (items, w, _, _) in enumerate(lays):
        lx = dx0 + {"left": 0.0, "center": (block_w - w) / 2, "right": block_w - w}.get(ma, 0.0)
        ly = dy0 - li * lh
        for txt, k, xo in items:
            ox, oy = lx + xo + offset[0], ly + offset[1]
            rx, ry = ox * c - oy * sn, ox * sn + oy * c
            tr = trans + ScaledTranslation(rx / 72.0, ry / 72.0, fig.dpi_scale_trans)
            arts.append(ax.text(x, y, txt, transform=tr, rotation=rotation, **k))
    return arts


def math_labels(texts):
    """Typeset existing Text objects whose whole content is one $...$ segment (tick labels, titles) with LaTeX.

    A label that mixes sans text and math must be drawn with mixed_text instead; that raises a ValueError here."""
    _ensure_preamble()
    for t in texts:
        s = t.get_text()
        if not has_math(s):
            continue
        segs = split_math(s.strip())
        if len(segs) != 1 or not segs[0][1]:
            raise ValueError(f"{s!r} mixes text and math; draw it with mixed_text")
        if shutil.which("latex"):
            _ensure_math_size(t.get_fontsize())
            t.set_usetex(True)
        else:
            _warn_once("nolatex", "latex not found: math drawn with mathtext (Computer Modern), not LaTeX")
            t.set_math_fontfamily("cm")
    return texts


def mixed_box(s, fontsize=None, color=None, **kw):
    """The label as an OffsetBox (segments on one baseline), for legends, AnchoredOffsetbox or AnnotationBbox."""
    import matplotlib as mpl
    from matplotlib.offsetbox import HPacker, TextArea
    _ensure_preamble()
    fontsize = mpl.rcParams["legend.fontsize"] if fontsize is None else fontsize
    try:
        fontsize = float(fontsize)
    except (TypeError, ValueError):
        from matplotlib.font_manager import FontProperties
        fontsize = FontProperties(size=fontsize).get_size_in_points()
    kids = []
    for seg, is_math in _pieces(s):
        if seg == " " and not is_math:
            txt, k = " ", dict(kw, fontsize=fontsize, usetex=False)
            if color is not None:
                k["color"] = color
            kids.append(TextArea(" ", textprops=k))
            continue
        txt, k = _text_kw(kw, fontsize, color, is_math, seg)
        if is_math and k.get("usetex"):
            _ensure_math_size(fontsize)
        for drop in ("ha", "va", "rotation_mode"):
            k.pop(drop, None)
        kids.append(TextArea(txt, textprops=k))
    return HPacker(children=kids, align="baseline", pad=0, sep=0)


def mixed_legend(leg):
    """Rebuild the legend entries that contain $...$ as baseline-aligned mixed boxes (sans text + LaTeX math)."""
    from matplotlib.offsetbox import HPacker
    texts = list(leg.get_texts())
    try:
        rows = [r for col in leg._legend_handle_box.get_children() for r in col.get_children()]
    except AttributeError:
        rows = []
    done = 0
    for t in texts:
        s = t.get_text()
        if not has_math(s):
            continue
        box = mixed_box(s, fontsize=t.get_fontsize(), color=t.get_color(), fontweight=t.get_fontweight(),
                        fontstyle=t.get_fontstyle(), fontfamily=t.get_fontfamily())
        row = next((r for r in rows if isinstance(r, HPacker) and any(getattr(ch, "_text", None) is t for ch in r.get_children())), None)
        if row is None:            # unknown legend layout: fall back to LaTeX for the whole entry
            t.set_usetex(True)
            continue
        row._children = [box if getattr(ch, "_text", None) is t else ch for ch in row.get_children()]
        box.set_figure(leg.figure)
        t.set_visible(False)
        done += 1
    leg.stale = True
    return done


# ----------------------------------------------------------------------------- saving and checks


def rasterize_pdf(pdf, png, dpi=300):
    """PNG from the PDF (PyMuPDF, else pdftoppm): previews of usetex figures without dvipng."""
    try:
        import pymupdf
        doc = pymupdf.open(str(pdf))
        doc[0].get_pixmap(dpi=dpi).save(str(png))
        doc.close()
        return True
    except ImportError:
        pass
    if shutil.which("pdftoppm"):
        stem = str(Path(png).with_suffix(""))
        subprocess.run(["pdftoppm", "-png", "-singlefile", "-r", str(dpi), str(pdf), stem], check=True)
        return True
    raise RuntimeError("cannot rasterize the PDF: install PyMuPDF (pip install pymupdf) or poppler (pdftoppm)")


def save_figure(fig, path, formats=("pdf", "png"), dpi=300, check=True, printed_scale=1.0, tex_ticks=True, **kw):
    """Save PDF (vector, Type 1 / TrueType fonts) and PNG; the PNG is rasterized from the PDF when dvipng is missing.

    printed_scale: printed width / figure width (1.0 when figsize is the printed size).
    tex_ticks: typeset pure-math tick labels (log axes) with LaTeX first (tex_ticklabels). Returns the saved paths."""
    if tex_ticks and shutil.which("latex"):
        _ensure_preamble()
        tex_ticklabels(fig)
    stem = Path(path)
    if stem.suffix.lower() in (".pdf", ".png", ".svg", ".eps"):
        stem = stem.with_suffix("")
    stem.parent.mkdir(parents=True, exist_ok=True)
    kw.setdefault("metadata", {"CreationDate": None} if "pdf" in formats else None)
    out = []
    pdf = stem.with_suffix(".pdf")
    if "pdf" in formats or "png" in formats:
        fig.savefig(pdf, **{k: v for k, v in kw.items() if v is not None})
        if "pdf" in formats:
            out.append(pdf)
    for fmt in formats:
        if fmt in ("pdf",):
            continue
        p = stem.with_suffix("." + fmt)
        if fmt == "png":
            try:
                if not shutil.which("dvipng") and _uses_tex(fig):
                    raise RuntimeError("no dvipng")
                fig.savefig(p, dpi=dpi)
            except RuntimeError:
                rasterize_pdf(pdf, p, dpi)
        else:
            fig.savefig(p, **{k: v for k, v in kw.items() if k != "metadata"})
        out.append(p)
    if "pdf" not in formats and pdf.exists():
        pdf.unlink()
    if check and "pdf" in formats:
        report = check_pdf(pdf, printed_scale=printed_scale)
        for lvl, msg in report["issues"]:
            (warnings.warn if lvl == "warn" else print)(f"{pdf.name}: {lvl}: {msg}")
        if any(l == "error" for l, _ in report["issues"]):
            raise RuntimeError(f"{pdf.name} failed the PDF check: " + "; ".join(m for l, m in report["issues"] if l == "error"))
    return out


def tex_ticklabels(fig):
    """Typeset tick labels that are pure math (e.g. log-axis '$\\mathdefault{10^{2}}$') with LaTeX, not mathtext.

    Draws the figure once to create the final ticks; call it after the layout is final (save_figure does)."""
    fig.canvas.draw()
    n = 0
    for ax in fig.axes:
        for axis in (ax.xaxis, ax.yaxis, getattr(ax, "zaxis", None)):
            if axis is None:
                continue
            for t in axis.get_ticklabels(which="both"):
                s = t.get_text().strip()
                if t.get_usetex() or not has_math(s):
                    continue
                segs = split_math(s)
                if len(segs) == 1 and segs[0][1]:
                    math_labels([t])
                    n += 1
    return n


def _uses_tex(fig):
    return any(t.get_usetex() for t in fig.findobj(lambda a: hasattr(a, "get_usetex")))


TEX_FONT_RE = re.compile(r"^(CM|LM|EU|MSAM|MSBM|NewTX|TX|PX|NewPX|STIX|Libertin|ZX|ZY|RSFS|BBM|DS|Euler|Fourier)", re.I)


def check_pdf(pdf, printed_scale=1.0, min_pt=5.0, warn_pt=6.0):
    """Fonts and printed text sizes of page 1 -> {'fonts': [...], 'sizes': {...}, 'issues': [(level, msg)]}.

    Errors: Type 3 fonts, text (math scripts included) below min_pt. Warnings: math scripts below warn_pt.
    LaTeX sizes are TeX points (5pt = 4.98bp), so the limits allow for that."""
    issues, fonts, sizes = [], [], {}
    try:
        import pymupdf
    except ImportError:
        pymupdf = None
    if pymupdf is not None:
        doc = pymupdf.open(str(pdf))
        for f in doc.get_page_fonts(0, full=True):
            fonts.append((re.sub(r"^[A-Z]{6}\+", "", f[3]), f[2]))
        for b in doc[0].get_text("rawdict")["blocks"]:
            for ln in b.get("lines", []):
                for sp in ln["spans"]:
                    name = re.sub(r"^[A-Z]{6}\+", "", sp["font"])
                    sizes.setdefault(name, set()).add(round(sp["size"] * printed_scale, 2))
        doc.close()
    elif shutil.which("pdffonts"):
        r = subprocess.run(["pdffonts", str(pdf)], capture_output=True, text=True)
        for line in r.stdout.splitlines()[2:]:
            tok = line.split()
            if len(tok) >= 7:
                fonts.append((re.sub(r"^[A-Z]{6}\+", "", tok[0]), " ".join(tok[1:-6]) if len(tok) > 7 else tok[1]))
    else:
        issues.append(("warn", "cannot check fonts: install PyMuPDF (pip install pymupdf) or poppler (pdffonts)"))
    t3 = sorted({n for n, t in fonts if t.replace(" ", "").lower() == "type3"})
    if t3:
        issues.append(("error", f"Type 3 fonts {', '.join(t3)}; set rcParams['pdf.fonttype'] = 42 (setup_math does) and "
                                "use TrueType/OpenType text fonts"))
    tol = 72.0 / 72.27
    for name, ss in sorted(sizes.items()):
        lo = min(ss)
        if lo < min_pt * tol - 0.01:
            issues.append(("error", f"{name} text at {lo:g}pt (min {min_pt:g}pt printed); raise the base size or declare "
                                    "larger math sizes, never shrink or fake scripts"))
        elif TEX_FONT_RE.match(name) and lo < warn_pt * tol - 0.01:
            issues.append(("warn", f"math font {name} at {lo:g}pt (LaTeX script size; want >= {warn_pt:g}pt where space allows)"))
    return {"fonts": fonts, "sizes": {k: sorted(v) for k, v in sizes.items()}, "issues": issues}
