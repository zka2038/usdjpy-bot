"""Project-wide settings."""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
SYMBOL = "USDJPY"

# Out-of-sample holdout. Nothing on/after this date is used until a strategy has passed on
# earlier data and its spec is frozen. Pass allow_holdout=True only for the final check.
HOLDOUT_START = "2025-01-01"
