"""Parser and comparison checks for champions.sources, on tiny hand-made HTML (no network)."""
import unittest

from champions.sources import common, compare, championslab, munchstats, pikalytics

MUNCH = """<h2>Moves</h2><ul><li><button><span class="left-text">Protect</span>
<span class="right-text">80.9%</span></button></li></ul>
<h2>Items</h2><ul><li><button><div class="image-item"><span class="left-text" style="x">Life Orb</span></div>
<span class="right-text">22.1%</span></button></li></ul>
<h2>Stat Point Spreads</h2><ul><li><span class="left-text">2/32/0/0/0/32</span><span class="right-text">22.4%</span></li></ul>
<span class="info-stat-label">Rank</span> <span class="info-stat-value">#6</span>
<span id="champions-updated-value">October 06, 2026 at 12:07 UTC</span>
<button onclick="selectPokemon('Rillaboom')"><span class="right-text">#1</span>
<button onclick="selectPokemon('Sneasler')"><span class="right-text">#2</span>"""

PIKA = """<div class="pokemon-ind-summary-title">Usage Percent</div><div class="x">21<span>%</span></div>
<div class="pokemon-ind-summary-title">Monthly Rank</div><div class="x"><span>#</span>4</div>
<div id="moves_wrapper"><div class="pokedex-move-entry-new"><div class="pokedex-inline-text-offset">Protect</div>
<div class="pokedex-inline-right">29.158%</div></div></div>
<div id="teammate_wrapper"><a class="teammate_entry pokedex-move-entry-new" data-name="Incineroar" href="/x">
<div class="pokedex-inline-right">38.075%</div></a></div>
<div id="items_wrapper"><div class="pokedex-move-entry-new"><div class="pokedex-inline-text">Life Orb</div>
<div class="pokedex-inline-right">33.361%</div></div></div>
<div id="abilities_wrapper"><div class="pokedex-move-entry-new"><div class="pokedex-inline-text">Rough Skin</div>
<div class="pokedex-inline-right">92.741%</div></div></div>"""


class SourcesTests(unittest.TestCase):
    def test_key(self):
        self.assertEqual(common.key("Mr. Rime"), common.key("mr-rime"))
        self.assertEqual(common.key("Garchomp-Mega-Z"), "garchompmegaz")

    def test_munchstats(self):
        e = munchstats.parse(MUNCH)
        self.assertEqual(e["moves"], {"Protect": 80.9})
        self.assertEqual(e["items"], {"Life Orb": 22.1})      # name nested in a sprite <div>
        self.assertEqual(e["spreads"], {"2/32/0/0/0/32": 22.4})
        self.assertEqual((e["rank"], e["as_of"]), (6, "October 06, 2026 at 12:07 UTC"))
        self.assertEqual(munchstats.roster(MUNCH), {"Rillaboom": 1, "Sneasler": 2})

    def test_pikalytics(self):
        e = pikalytics.parse(PIKA)
        self.assertEqual(e["moves"], {"Protect": 29.158})
        self.assertEqual(e["teammates"], {"Incineroar": 38.075})
        self.assertEqual(e["items"], {"Life Orb": 33.361})
        self.assertEqual(e["abilities"], {"Rough Skin": 92.741})
        self.assertEqual((e["usage"], e["rank"]), (21.0, 4))

    def test_championslab_empty_page(self):
        d = championslab.parse("<html></html>")
        self.assertEqual((d["usage"], d["teams"]), ([], []))

    def test_spearman(self):
        a = {"x": 1, "y": 2, "z": 3, "w": 4}
        self.assertEqual(compare.spearman(a, a)[0], 1.0)
        self.assertEqual(compare.spearman(a, {"x": 4, "y": 3, "z": 2, "w": 1})[0], -1.0)
        self.assertIsNone(compare.spearman({"x": 1}, {"x": 1})[0])

    def test_move_agreement(self):
        s = lambda m: {"pokemon": {"a": {"moves": m}}}
        ov, df = compare.move_agreement(s({"p": 50, "q": 40, "r": 30, "s": 20}), s({"p": 40, "q": 40, "r": 30, "t": 10}))
        self.assertEqual((ov, df), ([3], [10 / 3]))


if __name__ == "__main__":
    unittest.main()
