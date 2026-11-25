"""Screenshot scanner checks. Skipped without Pillow/numpy or without the icons (`champions sources icons`)."""
import unittest
from pathlib import Path

try:
    import numpy  # noqa: F401
    from PIL import Image
    from champions.vision import scan
except ImportError:                                  # pragma: no cover
    scan = None

FIXTURE = Path(__file__).parent / "fixtures" / "teamselect_opponents.png"
HAVE_ICONS = scan is not None and any(scan.ICONS.glob("*.png"))
# Read by eye from the screenshot (the game shows no names for the opponent): Noivern, Lycanroc (form
# not distinguishable), Politoed, Rotom (electric/ghost badges), Kangaskhan, Hippowdon.
EXPECTED = ["noivern", "lycanroc", "politoed", "rotom", "kangaskhan", "hippowdon"]


@unittest.skipUnless(HAVE_ICONS, "needs Pillow, numpy and sources/icons/")
class ScanTests(unittest.TestCase):
    def species(self, res):
        names = []
        for s in res["slots"]:
            top = s["candidates"][0]["name"] if s["candidates"] else ""
            names.append(top.split("-")[0] if top.startswith("lycanroc") else top)
        return names

    def test_fixture(self):
        res = scan.scan(str(FIXTURE))
        self.assertEqual(self.species(res), EXPECTED)

    def test_form_ambiguity_flagged(self):
        slot = scan.scan(str(FIXTURE))["slots"][1]
        self.assertTrue(slot["uncertain"])
        self.assertEqual({c["name"] for c in slot["candidates"][:3]},
                         {"lycanroc-dusk", "lycanroc-midday", "lycanroc-midnight"})

    def test_other_16x9_sizes(self):
        for size in [(1280, 720), (1920, 1080)]:
            im = Image.open(FIXTURE).resize(size, Image.LANCZOS)
            res = scan.scan(self._png(im))
            self.assertEqual(self.species(res), EXPECTED, size)

    def test_badges_read(self):
        types = [s["types"] for s in scan.scan(str(FIXTURE))["slots"]]
        self.assertEqual(types[0], ["flying", "dragon"])
        self.assertEqual(types[3], ["electric", "ghost"])

    def test_rejects_non_16x9_and_junk(self):
        with self.assertRaises(ValueError):
            scan.scan(self._png(Image.new("RGB", (800, 800))))
        with self.assertRaises(ValueError):
            scan.scan(b"not an image")

    @staticmethod
    def _png(im):
        import io
        buf = io.BytesIO()
        im.save(buf, "PNG")
        return buf.getvalue()


if __name__ == "__main__":
    unittest.main()
