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
| `san_onofre_bluffs` | San Onofre SB — Bluffs | San Clemente, at the county line | 175 | Rustic: no hookups, chemical toilets, cold showers. Online booking mid-Mar→mid-Sep only. Watched in local runs; not in the k8s ConfigMap. |
| `san_elijo_group` | San Elijo — Grunion Run group site | Encinitas | 1 | Single group site (#128), so there is no "adjacent pair". Disabled; documented for completeness. |

Site maps and park pages:

```bash
python -m campscout maps               # print the links
python -m campscout maps --download    # save the PDFs locally
```

There is also a `sites` command that dumps the **live** site roster from the
API with the desirability score this tool assigns each one — a more useful
"which sites matter" view than the PDF. (It has a coordinates column, but the
current backend returns none — see "Reality check" below.)

## Quick start

```bash
git clone https://git.scottyah.com/scottyah/campscout.git
cd campscout
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

## Docker / Kubernetes

```bash
docker build -t campscout:latest .

docker run --rm \
  -v campscout-state:/var/lib/campscout \
  -v $PWD/config.yaml:/etc/campscout/config.yaml:ro \
  campscout:latest scan
```

The image runs as UID 10001, needs no writable root filesystem, and reads its
paths from `CAMPSCOUT_CONFIG` / `CAMPSCOUT_CAMPGROUNDS` so both files can come
from read-only mounts. `scan` is the default command; pass `watch` for a
long-running container (it handles SIGTERM and finishes the current pass, so
`docker stop` is clean rather than a 10-second wait for SIGKILL).

For Kubernetes this deploys like the other apps: push to git.scottyah.com and
Gitea Actions does the rest (`.gitea/workflows/deploy.yaml` builds the image
with buildah, pushes it to `harbor.scottyah.com/secure/campscout`, creates the
`campscout-secrets` and `harborcred` Secrets from the sops-encrypted
`.env.encrypted`, pins the image to the commit SHA, and applies `k8s.yaml`).

One-time setup — secrets only (facility IDs are already resolved and baked
into `k8s.yaml`, see below):

```bash
# Copy .env.example to .env, fill in NTFY_TOPIC (heartbeat URL optional),
# then run ./ship.sh (encrypts, commits, pushes).
# The Gitea org secrets (SOPS_AGE_KEY / HARBOR_* / KUBECONFIG_DATA)
# must be visible to this repo.
```

Day-to-day is `./ship.sh` after changing secrets, or a plain `git push` for
code changes; either triggers a build and deploy. Manual
`kubectl apply -f k8s.yaml` still works — the header comment in that file
covers creating the two Secrets by hand first.

It ships a CronJob (every 10 min) plus a commented Deployment alternative for
in-process `watch`. Use one or the other — they share a ReadWriteOnce volume.

### Operating it on the cluster

```bash
kubectl -n campscout get jobs                          # recent scans: want Complete, not Failed
kubectl -n campscout logs -l app=campscout --tail=50   # what the last scan saw
kubectl -n campscout delete jobs --field-selector status.successful=0   # clear failed history
```

To prove alerts reach your phone, run `test-notify` with the CronJob's own pod
spec (it carries the pull secret, config mount, and ntfy Secret — a bare
`kubectl run` has none of those and will hang or fall back to console):

```bash
kubectl -n campscout create job test-notify --from=cronjob/campscout --dry-run=client -o json \
  | jq '.spec.template.spec.containers[0].args = ["test-notify"]' \
  | kubectl -n campscout apply -f -
kubectl -n campscout wait --for=condition=complete job/test-notify --timeout=120s
kubectl -n campscout logs job/test-notify
kubectl -n campscout delete job test-notify
```

### If pods can't pull the image

CI skips the image build when only infra files changed — which assumes some
earlier run already pushed an image. On a brand-new repo whose first runs
failed before the build step, a later docs-only push goes green while the
manifests point at an image that doesn't exist (pods sit in ImagePullBackOff
while the pipeline looks healthy). Recovery: **Run workflow** (manual
dispatch) on the Actions page — dispatch always builds, precisely for this
case. New-repo checklist while you're there: the Gitea Actions secrets
(`SOPS_AGE_KEY`, `HARBOR_USERNAME`, `HARBOR_PASSWORD`, `KUBECONFIG_DATA`) are
not inherited from other repos unless they're set at the user level.

Three things in there are load-bearing rather than boilerplate:

- **The PVC is not optional.** State holds the alert dedupe table. On ephemeral
  storage it resets every run, so one open pair re-alerts every 10 minutes
  forever, and `status` can never tell you whether scans are happening.
- **`concurrencyPolicy: Forbid`.** Two overlapping scans race the state file on
  a ReadWriteOnce volume.
- **The liveness probe uses `status --check`, not plain `status`.** A Deployment
  has no cron or systemd timer, so plain `status` would report "nothing
  scheduled", exit non-zero, and restart-loop a perfectly healthy pod.

A scan that reaches zero campgrounds exits non-zero, so a broken ConfigMap
surfaces as a failed Job instead of a green one that quietly never checks
anything.

### About the facility IDs

`place_id` / `facility_ids` originally shipped as `null` because they couldn't
be verified against the live API — a wrong hardcoded facility ID doesn't
error, it silently scans the wrong campground. They were resolved for real via
`discover --write` on 2026-08-12, against the current (Tyler-hosted) backend.
A park is usually split into several per-section "facilities" — San Elijo is
three — and `facility_ids` lists all of them, because watching one section
silently misses the rest (San Elijo's bluff-front row lives in a different
facility than the discover default would have picked).

Re-run `python -m campscout discover --write` any time to re-verify; there are
tests that fail if the IDs stop looking real. For parks whose name covers two
physical campgrounds (San Onofre SB is both Bluff Camp and San Mateo Camp,
with overlapping site numbers), `facility_match` in `data/campgrounds.yaml`
pins discovery to the right one.

## How "adjacent" is decided

Site numbering is *usually* sequential along a loop, so 82 and 83 are neighbors.
That heuristic fails both ways, and both matter:

- **False positives** — consecutive numbers that aren't neighbors, because the
  numbering wraps to a new loop or jumps the park road. Fixed with `groups`
  (only pair within a loop) and `breaks` (specific non-neighbor pairs).
- **False negatives** — real neighbors with non-consecutive numbers, e.g. odd
  and even rows facing each other. Fixed with `extra_pairs`.

When the API returns coordinates, the tool skips the guessing and measures
actual distance instead. The current (Tyler-hosted) backend returns none, so
in practice the numeric test is the one that fires; `mode: either` (the
default) accepts a pair if *either* test passes, which also means geo kicks
back in by itself if coordinates ever return:

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

**Reality check (2026-08-12):** the live API — now hosted on Tyler
Technologies' platform — returns `Latitude: 0.0, Longitude: 0.0` for every
site, so the geo rule currently never fires and `scan` warns loudly when a
configured geo rule is inert. `san_elijo`'s hand-written tiers are unaffected.
`south_carlsbad` and `san_onofre_bluffs` had no tiers, so their `default` is
set to 85: any open adjacent pair there alerts. To prefer the oceanfront row
again, read the camp map, then add `tiers` by site number (check the roster
with `campscout sites south_carlsbad`).

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

79 tests, no network. Because the live API was unreachable while first building
this, `tests/test_end_to_end.py` runs the whole pipeline — grid parsing,
scoring, adjacency, dedupe, message formatting — against a stubbed backend with
a realistic payload, including the no-coordinates path that turned out to be
the live backend's actual behavior.

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
