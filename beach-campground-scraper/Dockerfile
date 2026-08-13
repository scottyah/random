# syntax=docker/dockerfile:1
#
# Build:  docker build -t campscout:latest .
# Run:    docker run --rm -v campscout-data:/var/lib/campscout \
#           -v $PWD/config.yaml:/etc/campscout/config.yaml:ro campscout:latest scan
#
# The image runs as an unprivileged user and needs no writable root
# filesystem, so it drops straight into a hardened pod spec.

# ---- builder: resolve deps into a self-contained venv -------------------
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY requirements.txt .

# Only pure-python/wheel deps (requests, PyYAML), so no compiler needed here.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ---- runtime -----------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="campscout" \
      org.opencontainers.image.description="Watches North County San Diego beach campgrounds for two adjacent open sites" \
      org.opencontainers.image.source="https://github.com/scottyah/random"

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CAMPSCOUT_CONFIG=/etc/campscout/config.yaml \
    CAMPSCOUT_CAMPGROUNDS=/etc/campscout/campgrounds.yaml

# ca-certificates is genuinely needed: every call is HTTPS to the
# ReserveCalifornia API, and python:slim ships without the CA bundle refreshed.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --create-home --home-dir /home/campscout campscout

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY campscout/ ./campscout/
COPY data/campgrounds.yaml /etc/campscout/campgrounds.yaml
COPY config.example.yaml /etc/campscout/config.example.yaml

# State lives here and is the ONLY path that must be writable. Mount a volume
# over it: without persistence the dedupe table resets every run and you get
# re-alerted about the same pair forever.
RUN mkdir -p /var/lib/campscout && chown -R campscout:campscout /var/lib/campscout
VOLUME ["/var/lib/campscout"]

USER 10001:10001

# `scan` is one-shot and the right default for a CronJob. Override with
# `watch` for a long-running Deployment.
ENTRYPOINT ["python", "-m", "campscout"]
CMD ["scan"]
