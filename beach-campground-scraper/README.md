# campscout

Watches North County San Diego beach campgrounds and alerts you when **two
adjacent, desirable sites** open up at once — which is the hard part, because
these places are booked out months ahead and the only realistic way in is
catching a cancellation.

All four campgrounds are California State Parks, so they share one booking
backend (ReserveCalifornia / UseDirect) and one scraper covers all of them.

## The campgrounds

| Key | Campground | Where | Sites | Notes |
|---|---|---|---|---|
| `san_elijo` | San Elijo State Beach | Cardiff-by-the-Sea, Encinitas | ~170 | Low bluff directly above the sand, stairs to the beach. The prize. |
| `south_carlsbad` | South Carlsbad State Beach | Carlsbad | ~220 | Long linear bluff strip, ~30 min north of downtown. Ponto beach at both ends. |
| `san_onofre_bluffs` | San Onofre SB — Bluffs | San Clemente, at the county line | 175 | Rustic: no hookups, chemical toilets, cold showers. Online booking mid-Mar→mid-Sep only. Off by default. |
| `san_elijo_group` | San Elijo — Grunion Run group site | Encinitas | 1 | Single group site (#128), so there is no "adjacent pair". Disabled; documented for completeness. |

Site maps and park pages:

```bash
python -m campscout maps               # print the links
python -m campscout maps --download    # save the PDFs locally
```

Note that `data/campgrounds.yaml` also has a `sites` command that dumps the
**live** site roster from the API — that's a more useful "site map" than the
PDF, because it includes real per-site coordinates and the desirability score
this tool assigns each one.

## Quick start

```bash
git clone <this repo>
cd beach-campground-scraper
./deploy/install.sh          # venv, deps, tests, ID discovery, systemd timer
```

Then confirm it's actually watching:

```bash
python -m campscout status
```

Manual equivalent, if you'd rather do it step by step:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml

python -m campscout discover --write   # resolve real ReserveCalifornia IDs
python -m campscout sites san_elijo    # see what it found
python -m campscout test-notify        # prove alerts reach you
python -m campscout scan               # one pass
python -m campscout status             # is it healthy?
```

## Knowing it's actually running

The trap with a notify-only watcher: **silence is ambiguous.** No alerts might
mean no adjacent sites opened up, or it might mean the scraper died weeks ago.
Three things keep those distinguishable:

**`campscout status`** — the direct answer:

```
====================================================================
  OK — last successful scan 4 min ago
====================================================================

Scan history
  last success   : 4 min ago
  total scans    : 1249
  sites checked  : 392 (last run)
  alerts sent    : 3 total, last 2.1 days ago

What it is watching
  [ok            ] San Elijo State Beach
  [ok            ] South Carlsbad State Beach
  52 candidate stays, min_score 85, 180d horizon

Scheduling
  systemd timer campscout.timer: active
```

It exits non-zero when something is wrong, so `campscout status || alert-me`
works in a cron of its own. On a fresh checkout it says `NOT RUNNING` and lists
exactly what's missing.

**A failed scan is never mistaken for a quiet one.** If no campground could be
reached, that's recorded as a failure, not as "nothing available" — so a
persistent API outage shows up as `STALE` rather than looking healthy.

**A dead-man's switch**, which is the only part that survives the host itself
dying. A watcher can't tell you it stopped — if it's dead it isn't sending
anything. So invert it: ping an outside service after each successful scan and
let that service alert you when pings stop.

```yaml
heartbeat:
  url: ${CAMPSCOUT_HEARTBEAT_URL}    # e.g. a healthchecks.io ping URL (free)
```

Without this, a powered-off server is indistinguishable from a fully-booked
campground. `status` warns when it isn't configured.

### Step 1 is required

`place_id` and `facility_id` ship as `null` on purpose. I built this in an
environment whose egress policy blocked `calirdr.usedirect.com`, so I could not
verify the IDs against the live API — and a wrong hardcoded facility ID doesn't
error, it silently scans the wrong campground and never alerts you. `discover`
resolves them for real from your server. There's a test that fails if anyone
pastes in an unverified ID.

If `discover` can't match a park automatically, run it without `--write`, read
the table, and paste the IDs into `data/campgrounds.yaml` by hand.

## How "adjacent" is decided

Site numbering is *usually* sequential along a loop, so 82 and 83 are neighbors.
That heuristic fails both ways, and both matter:

- **False positives** — consecutive numbers that aren't neighbors, because the
  numbering wraps to a new loop or jumps the park road. Fixed with `groups`
  (only pair within a loop) and `breaks` (specific non-neighbor pairs).
- **False negatives** — real neighbors with non-consecutive numbers, e.g. odd
  and even rows facing each other. Fixed with `extra_pairs`.

When the API returns coordinates, the tool skips the guessing and measures
actual distance instead. `mode: either` (the default) accepts a pair if *either*
test passes:

```yaml
adjacency:
  mode: either          # numeric | geo | either
  max_meters: 35        # geo threshold
  groups: ["1-43", "44-99"]
  breaks: ["43-44"]     # consecutive but not neighbours
  extra_pairs: ["47-49"]
```

In `breaks`/`extra_pairs` a dash means **and**, not a range: `"47-49"` is the
pair {47, 49}. In `sites:` specs elsewhere a dash *is* a range, so `"47-49"`
there means 47, 48, 49.

## How "desirable" is decided

Two mechanisms that compose:

**Explicit tiers**, for what you already know. First match wins, so order them
best-first:

```yaml
desirability:
  default: 15
  tiers:
    - {score: 100, label: bluff-front, sites: "145-171"}
    - {score: 90,  label: ocean side,  sites: "1-43"}
  exclude:
    sites: "94,128"     # hike-and-bike, group site
```

**A geo rule**, for what you don't. All of these campgrounds are linear strips
running north–south along the coast, so the oceanfront row is simply the
westernmost sites. Once `discover` has pulled coordinates, this classifies the
good sites with nobody hand-maintaining a range list:

```yaml
  geo:
    mode: west_percentile
    percentile: 35        # westernmost 35% are "oceanfront"
    score: 100
```

The geo rule only ever *raises* a score, so hand-curated tiers stay
authoritative. It's skipped entirely if fewer than 8 sites have coordinates,
where the percentile split would be noise.

`san_elijo`'s tiers come from published site-number ranges (bluff-front 145–171,
ocean side 1–43). `south_carlsbad` deliberately has **no** hand-written ranges —
I couldn't verify them, so it relies on the geo rule, which is reliable for a
strip campground. Add tiers there yourself after looking at `campscout sites
south_carlsbad`.

## Search windows

```yaml
search:
  min_score: 85          # both sites must clear this
  horizon_days: 180      # ReserveCalifornia opens bookings 6 months out
  windows:
    - {label: weekend,      nights: 2, weekdays: [4]}   # Mon=0, so 4 = Friday
    - {label: long weekend, nights: 3, weekdays: [4]}
    - {label: labor day,    nights: 3, checkin: '2026-09-04'}
```

A site only counts if it's free for **every** night of the stay.

## Notifications

`console`, `ntfy` (phone push, no account needed), `email` (SMTP), and
`webhook` (Slack/Discord). Configure any combination in `config.yaml`; secrets
come from the environment via `${VAR}`.

Repeat alerts for the same pair+dates are suppressed for `cooldown_hours`
(default 12). If every notifier fails, state is left untouched so the next pass
retries rather than silently burning the alert.

## Deploying

Cron, every 10 minutes:

```cron
*/10 * * * * cd /srv/campscout && .venv/bin/python -m campscout scan >> /var/log/campscout.log 2>&1
```

Or systemd — `deploy/campscout.service` and `deploy/campscout.timer` are
included:

```bash
sudo cp deploy/campscout.* /etc/systemd/system/
sudo systemctl enable --now campscout.timer
```

Be a reasonable citizen: the default is one pass per 10 minutes with a 1s gap
between API calls and jitter on the loop. `watch` refuses to poll faster than
120s. Cancellations don't appear often enough to justify hammering it.

## About auto-booking

You asked for "buys or notifies me". This ships the notify half, and
deliberately stops short of auto-purchase. Two reasons, neither of them
squeamishness:

1. It needs your ReserveCalifornia login and a stored payment method to
   complete a checkout unattended. That's a meaningfully different security
   posture than a read-only scraper, and not something to add without you
   explicitly deciding you want it on your server.
2. Automated booking is a good way to get an account flagged. ReserveCalifornia
   is not friendly to it.

What's here instead: the alert includes a direct booking link, and it fires the
moment a pair appears. For a cancellation you're realistically competing over
minutes, not seconds, so a phone push with a one-tap link is close to as good in
practice.

If you do want real auto-booking, it's a self-contained addition — a `Booker`
that logs in, holds the two sites in the cart, and checks out — plugged in where
`dispatch()` is called in `cli._run_once`. Say the word and I'll build it; I'd
want to talk through credential storage first.

## Tests

```bash
python -m unittest discover -s tests
```

63 tests, no network. Because the live API was unreachable while building this,
`tests/test_end_to_end.py` runs the whole pipeline — grid parsing, scoring,
adjacency, dedupe, message formatting — against a stubbed backend with a
realistic payload, including the fallback path where the API returns no
coordinates.

## Layout

```
campscout/
  providers/reserve_california.py   API client (grid, discovery, chunking, retries)
  adjacency.py                      "are these two sites next to each other"
  desirability.py                   "is this site worth alerting on"
  scan.py                           availability → stays → pairs
  notify.py                         console / ntfy / email / webhook
  state.py                          dedupe + cooldown
  config.py                         YAML loading, ${ENV} expansion
  cli.py                            campgrounds, maps, discover, sites, scan, watch
data/campgrounds.yaml               curated campground + site knowledge
config.example.yaml                 your settings; copy to config.yaml
```
