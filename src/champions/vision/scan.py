"""Read the opponent's six Pokémon off a Switch capture of the Doubles/Singles team-select screen.

Run:  champions scan shot.png [--json] [--megas]

The opponent column shows sprites only (no names), so each of the six cards is cropped, the sprite is
cut out from the flat card background, and compared with the reference icons in sources/icons/ (fetch
them with `champions sources icons`). Match score = mask overlap (IoU) x colour similarity on the
overlap, after both sprites are fitted into the same small square. Needs Pillow and numpy.

Layout is stored as fractions of the 1650x928 reference frame, so any 16:9 capture size works. Only
clean screenshots are supported (no skew correction). A slot is `uncertain` when the best two
candidates are close, so the UI can ask for a manual pick instead of guessing.
"""
import io
import json
import sys
from pathlib import Path

NEEDS = "scan needs Pillow and numpy: pip install -e .[vision]"
ICONS = Path(__file__).resolve().parents[3] / "sources" / "icons"
PKG = Path(__file__).resolve().parents[1]
TYPE_ICONS = PKG / "play" / "static" / "icons"      # same artwork as the in-game type badges
BADGE_X = [(0.626, 0.772), (0.793, 0.942)]          # two badge slots; a single type uses the right one
BADGE_Y = (0.07, 0.51)
BADGE_PRESENT = 0.35                                # fraction of non-background pixels
BADGE_MAX_DIST = 1.3                                # combined distance above which a badge is unreadable
BADGE_SLACK = 0.2                                   # types this close to the best badge match stay plausible
REF_W, REF_H = 1650, 928
CARD_X = (1371 / REF_W, 1.0)                    # opponent column
CARD_TOP = [145 + 114.6 * i for i in range(6)]  # card tops in reference pixels
CARD_H = 100
SPRITE_X = (0.03, 0.62)                         # sprite lives left of the item/gender badges
SIDE = 48                                       # normalised square for comparison
BG_TOL = 60                                     # colour distance from card background = foreground
UNCERTAIN_MARGIN = 0.04
_LIB = {}


def _np():
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        raise SystemExit(NEEDS) from None
    return np, Image


def _fit(rgb, mask):
    """Crop to the mask's bounding box and centre it in a SIDExSIDE square (aspect kept).
    Returns (rgb SIDE*SIDE*3 float, mask SIDE*SIDE bool) or None when the mask is empty/tiny."""
    np, Image = _np()
    ys, xs = np.where(mask)
    if len(ys) < 30:
        return None
    rgb, mask = rgb[ys.min():ys.max() + 1, xs.min():xs.max() + 1], mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    scale = (SIDE - 2) / max(mask.shape)
    size = (max(1, round(mask.shape[1] * scale)), max(1, round(mask.shape[0] * scale)))
    a = np.dstack([rgb, mask * 255]).astype("uint8")
    a = np.asarray(Image.fromarray(a).resize(size, Image.LANCZOS)).astype(float)
    out_rgb, out_mask = np.zeros((SIDE, SIDE, 3)), np.zeros((SIDE, SIDE), bool)
    y0, x0 = (SIDE - size[1]) // 2, (SIDE - size[0]) // 2
    out_rgb[y0:y0 + size[1], x0:x0 + size[0]] = a[..., :3]
    out_mask[y0:y0 + size[1], x0:x0 + size[0]] = a[..., 3] > 127
    return out_rgb, out_mask


def library(icons_dir=ICONS, megas=False):
    """{name: (rgb, mask)} for every usable icon; cached per (dir, megas)."""
    k = (str(icons_dir), megas)
    if k in _LIB:
        return _LIB[k]
    np, Image = _np()
    lib = {}
    for f in sorted(Path(icons_dir).glob("*.png")):
        if not megas and "-mega" in f.stem:
            continue
        im = np.asarray(Image.open(f).convert("RGBA"))
        fit = _fit(im[..., :3].astype(float), im[..., 3] > 127)
        if fit:
            lib[f.stem] = fit
    if not lib:
        raise SystemExit(f"no icons in {icons_dir}: run `champions sources icons`")
    _LIB[k] = lib
    return lib


def cards(im):
    """[(full card, sprite crop)] RGB arrays for the six opponent cards, scaled from the reference layout."""
    np, _ = _np()
    W, H = im.size
    out = []
    for top in CARD_TOP:
        x0, x1 = CARD_X
        card = im.convert("RGB").crop((round(x0 * W), round(top / REF_H * H),
                                       round(x1 * W), round((top + CARD_H) / REF_H * H)))
        w = card.width
        full = np.asarray(card).astype(float)
        out.append((full, full[:, round(SPRITE_X[0] * w):round(SPRITE_X[1] * w)]))
    return out


def _bg(crop):
    np, _ = _np()
    border = np.concatenate([crop[:3].reshape(-1, 3), crop[-3:].reshape(-1, 3),
                             crop[:, :3].reshape(-1, 3), crop[:, -3:].reshape(-1, 3)])
    return np.median(border, axis=0)


_TYPES = {}
GLYPH_MIN = 170                                     # white glyph: every channel at least this bright


def _badge_feat(patch):
    """(fill colour, glyph mask) of a 16x16x3 badge patch: fill = median of non-white pixels."""
    np, _ = _np()
    glyph = patch.min(axis=2) > GLYPH_MIN
    rest = patch[~glyph]
    fill = np.median(rest, axis=0) if len(rest) else np.zeros(3)
    return fill, glyph


def type_library():
    """{type: (fill, glyph)} from the repo's own type icons, which are the in-game badge artwork."""
    if not _TYPES:
        np, Image = _np()
        for f in sorted(TYPE_ICONS.glob("*.png")):
            im = Image.open(f).convert("RGBA")
            n = im.width
            im = im.crop((round(n * .2), round(n * .2), round(n * .8), round(n * .8)))
            bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
            bg.alpha_composite(im)
            _TYPES[f.stem] = _badge_feat(np.asarray(bg.convert("RGB").resize((16, 16), Image.LANCZOS)).astype(float))
    return _TYPES


def classify_badge(patch):
    """[(distance, type)] best first. distance = fill-colour gap (0-1) + glyph shape mismatch (0-1)."""
    np, _ = _np()
    fill, glyph = _badge_feat(patch)
    out = []
    for t, (rfill, rglyph) in type_library().items():
        iou = (glyph & rglyph).sum() / max((glyph | rglyph).sum(), 1)
        out.append((float(np.abs(fill - rfill).mean() / 100 + (1 - iou)), t))
    return sorted(out)


def read_types(full):
    """Badges at the top right of a card -> one plausible-type set per badge present (best first within
    BADGE_SLACK of the closest), or None when no badge is readable."""
    np, Image = _np()
    h, w = full.shape[:2]
    bg = _bg(full[:, :round(SPRITE_X[1] * w)])
    found = []
    for x0, x1 in BADGE_X:
        b = full[round(BADGE_Y[0] * h):round(BADGE_Y[1] * h), round(x0 * w):round(x1 * w)]
        if b.size == 0 or (np.sqrt(((b - bg) ** 2).sum(axis=2)) > BG_TOL).mean() < BADGE_PRESENT:
            continue
        side = min(b.shape[:2])
        inner = b[round(side * .15):round(side * .85), round(side * .15):round(side * .85)]
        small = np.asarray(Image.fromarray(inner.astype("uint8")).resize((16, 16), Image.LANCZOS)).astype(float)
        ranked = classify_badge(small)
        if ranked[0][0] > BADGE_MAX_DIST:
            return None
        found.append([t for d, t in ranked if d <= min(ranked[0][0] + BADGE_SLACK, BADGE_MAX_DIST)])
    return found or None


def type_match(types, shown):
    """True if a species' type set fits the badges: same count, each badge's plausible set hit once."""
    if len(types) != len(shown):
        return False
    if len(shown) == 1:
        return next(iter(types)) in shown[0]
    a, b = sorted(types)
    return (a in shown[0] and b in shown[1]) or (b in shown[0] and a in shown[1])


def roster():
    """({name: type set}, {name: species}) from champions.json."""
    import json
    mons = json.loads((PKG / "data" / "champions.json").read_text())["pokemon"]
    return {p["name"]: set(p["types"]) for p in mons}, {p["name"]: p["species"] for p in mons}


def _components(mask, keep=0.05):
    """mask with only the connected pieces (8-neighbour) whose area is >= `keep` of the largest piece.
    Removes the thin light streaks across the card while keeping detached sprite parts (eyes, tips)."""
    np, _ = _np()
    h, w = mask.shape
    label = np.zeros((h, w), int)
    sizes = [0]
    for y0, x0 in zip(*np.where(mask)):
        if label[y0, x0]:
            continue
        sizes.append(0)
        n = len(sizes) - 1
        label[y0, x0] = n
        stack = [(y0, x0)]
        while stack:
            y, x = stack.pop()
            sizes[n] += 1
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not label[yy, xx]:
                        label[yy, xx] = n
                        stack.append((yy, xx))
    if len(sizes) == 1:
        return mask
    big = max(sizes)
    ok = np.array([False] + [z >= keep * big for z in sizes[1:]])
    return ok[label]


def cut(crop):
    """Sprite (rgb, mask) from a card crop: foreground = far from the card's border colour."""
    np, _ = _np()
    border = np.concatenate([crop[:3].reshape(-1, 3), crop[-3:].reshape(-1, 3),
                             crop[:, :3].reshape(-1, 3), crop[:, -3:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    dist = np.sqrt(((crop - bg) ** 2).sum(axis=2))
    mask = dist > BG_TOL
    # drop thin streaks / noise: keep rows and columns that hold a real amount of foreground
    mask &= (mask.sum(axis=1, keepdims=True) >= 3) & (mask.sum(axis=0, keepdims=True) >= 3)
    return _fit(crop, _components(mask))


def score(query, lib):
    """[(name, score)] best first. score = IoU of masks x (1 - mean colour difference on the overlap)."""
    np, _ = _np()
    rgb, mask = query
    names = list(lib)
    refs = np.stack([lib[n][0] for n in names])
    rmasks = np.stack([lib[n][1] for n in names])
    inter = rmasks & mask
    union = (rmasks | mask).sum(axis=(1, 2))
    iou = inter.sum(axis=(1, 2)) / np.maximum(union, 1)
    diff = np.abs(refs - rgb).mean(axis=3) / 255
    col = 1 - (diff * inter).sum(axis=(1, 2)) / np.maximum(inter.sum(axis=(1, 2)), 1)
    s = iou * col
    order = np.argsort(-s)
    return [(names[i], float(s[i])) for i in order]


def scan(source, icons_dir=ICONS, megas=False, top=5):
    """source: path or bytes of a screenshot -> {"slots": [{"slot", "candidates": [{"name","score"}], "uncertain"}]}."""
    np, Image = _np()
    try:
        im = Image.open(io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else source)
        im.load()
    except Exception as e:
        raise ValueError(f"not a readable image ({e})") from None
    if abs(im.width / im.height - REF_W / REF_H) > 0.03:
        raise ValueError(f"expected a 16:9 screenshot, got {im.width}x{im.height}")
    lib = library(icons_dir, megas)
    slots = []
    types, species = roster()
    for i, (full, crop) in enumerate(cards(im), 1):
        q = cut(crop)
        shown = read_types(full)
        pool = {n: v for n, v in lib.items() if n in types and type_match(types[n], shown)} if shown else lib
        ranked = score(q, pool or lib) if q else []
        # other forms of the best species (Lycanroc dusk/midday/...) can't be told apart by sprite: list them next
        forms = [r for r in ranked[1:] if ranked and species.get(r[0]) == species.get(ranked[0][0])]
        ranked = (ranked[:1] + forms + [r for r in ranked[1:] if r not in forms])[:max(top, 1 + len(forms))] if ranked else []
        slots.append({"slot": i, "types": [t[0] for t in shown] if shown else None,
                      "candidates": [{"name": n, "score": round(s, 3)} for n, s in ranked],
                      "uncertain": (not ranked) or bool(forms) or ranked[0][1] < 0.25
                      or (len(ranked) > 1 and ranked[0][1] - ranked[1][1] < UNCERTAIN_MARGIN)})
    return {"slots": slots}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    paths = [a for a in argv if not a.startswith("--")]
    if len(paths) != 1:
        sys.exit("usage: champions scan SCREENSHOT [--json] [--megas]")
    try:
        res = scan(paths[0], megas="--megas" in argv)
    except ValueError as e:
        sys.exit(str(e))
    if "--json" in argv:
        print(json.dumps(res, indent=1))
        return
    for s in res["slots"]:
        c = ", ".join(f"{x['name']} {x['score']:.2f}" for x in s["candidates"]) or "nothing found"
        print(f"{s['slot']}: {c}{'   (uncertain)' if s['uncertain'] else ''}")


if __name__ == "__main__":
    main()
