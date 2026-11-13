# champions (rebuild)

Fresh start. Usage-stat scrapers live in `src/champions/sources/`; see `sources/README.md`.

Known gap: `sources/opgg.py` still imports the old `champions.fetch.opgg` and `data/champions.json`, so `champions sources opgg` is broken until a roster source exists here.
