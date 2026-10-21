"""Fixed experimental settings: paths, test windows, sub-periods and seeds.

Sub-periods are fixed here, before any phase B result exists, so that cut-offs are not
chosen after seeing the errors.
"""

from __future__ import annotations

import os
from pathlib import Path

# BE_REPO_ROOT: the repository mounted in the Docker image, where the package is installed.
REPO_ROOT = Path(os.environ.get("BE_REPO_ROOT", Path(__file__).resolve().parents[2]))
RAW_DIR = REPO_ROOT / "data" / "raw"
CACHE_DIR = REPO_ROOT / "data" / "cache"  # raw ENTSO-E downloads, git-ignored
RESULTS_DIR = REPO_ROOT / "results"
MODELS_DIR = REPO_ROOT / "models"  # pickled production models, git-ignored

SEED = 2026
TZ = "Europe/Brussels"

# Phase A: test period of Lago et al. (2021) for BE, the last 2 x 364 days of BE.csv.
PHASE_A_TEST = ("2015-01-04", "2016-12-31")

# Phase B: continue the paper from the day after its test period. ENTSO-E data start in
# January 2015, so the 1456-day window is filled with BE.csv up to the day before JOIN_DAY,
# the first full delivery day of the Belgian price on ENTSO-E, where both sources agree.
PHASE_B_DOWNLOAD = ("2015-01-01", "2026-09-30")
JOIN_DAY = "2015-01-05"
PHASE_B_TEST = ("2017-01-01", "2026-09-30")
# SDAC clears 15-minute products from delivery day 1 October 2025; they are averaged to
# hours (data/calendar.py).
QUARTER_HOUR_START = "2025-10-01"

# Live forecasts: from the day after the phase B test period.
LIVE_START = "2026-10-01"

# Exogenous inputs, as in Lago et al. (2021) for Belgium: French day-ahead forecasts.
EXOGENOUS = ["Generation forecast FR", "Load forecast FR"]

PAPER_WINDOWS = (56, 84, 1092, 1456)
