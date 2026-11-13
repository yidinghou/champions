# Test fixtures

Real pages saved byte-for-byte (gzipped) on 2026-11-13, so parser tests run on what the sites actually serve:

| file | source URL |
|---|---|
| `munchstats-garchomp.html.gz` | https://www.munchstats.com/champions/doubles/Garchomp |
| `pikalytics-garchomp.html.gz` | https://www.pikalytics.com/pokedex/gen9championsvgc2026regmc/Garchomp |
| `championslab-meta.html.gz` | https://championslab.xyz/meta |

Fetched with `common.get` (the scrapers' own rate limits). To refresh after a site redesign, re-fetch with
`--refresh`, re-gzip over these files (`gzip.compress(data, 9, mtime=0)` keeps the bytes stable) and update the
expected values in `tests/test_sources.py`.
