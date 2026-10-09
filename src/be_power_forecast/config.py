"""Fixed experimental settings: paths, test windows, sub-periods and seeds.

Sub-periods are fixed here, before any phase B result exists, so that cut-offs are not
chosen after seeing the errors.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"
CACHE_DIR = REPO_ROOT / "data" / "cache"  # raw ENTSO-E downloads, git-ignored
RESULTS_DIR = REPO_ROOT / "results"
MODELS_DIR = REPO_ROOT / "models"  # pickled production models, git-ignored

SEED = 2026
TZ = "Europe/Brussels"

# Phase A: test period of Lago et al. (2021) for BE, the last 2 x 364 days of BE.csv.
PHASE_A_TEST = ("2015-01-04", "2016-12-31")

# Phase B: ENTSO-E data start in 2015; the 1456-day window needs 4 years of history.
PHASE_B_DOWNLOAD = ("2015-01-01", "2026-09-30")
PHASE_B_TEST = ("2019-01-01", "2026-09-30")
SUB_PERIODS = {
    "before": ("2019-01-01", "2021-06-30"),
    "crisis": ("2021-07-01", "2023-06-30"),
    "after": ("2023-07-01", "2026-09-30"),
    # Robustness split of "after": SDAC clears 15-minute products from delivery day
    # 1 October 2025.
    "after_hourly": ("2023-07-01", "2025-09-30"),
    "after_quarter_hour": ("2025-10-01", "2026-09-30"),
}
QUARTER_HOUR_START = "2025-10-01"

# Phase B exogenous sets; "FR" is the reference set, identical in nature to BE.csv.
EXOGENOUS_SETS = {
    "FR": ["Generation forecast FR", "Load forecast FR"],
    "BE": ["Wind and solar forecast BE", "Load forecast BE"],
    "FR+BE": [
        "Generation forecast FR",
        "Load forecast FR",
        "Wind and solar forecast BE",
        "Load forecast BE",
    ],
}

PAPER_WINDOWS = (56, 84, 1092, 1456)
