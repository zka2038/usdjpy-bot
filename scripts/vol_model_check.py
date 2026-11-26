"""Task 6: real-data checks of the volatility model (src/usdjpy/vol.py). Infrastructure only.

    python scripts/vol_model_check.py

Pre-holdout bars only. Nothing here predicts returns or tests a hypothesis, so it spends
no trial budget: it measures data coverage and how well volatility forecasts volatility.
1. Daily realised variance (5-min bid) on `combined`: valid days and median annualised
   vol by year.
2. HAR-RV out of sample, horizons 1 and 5: final coefficients, and MSE and QLIKE against
   the naive forecast (RV over the last h days carried forward).
3. Minute-of-week baseline coverage by clock, on HistData 2015-2024 1-min bid returns, and
   how each clock handles two real events (Thu 08:30 ET, 09:55 JST) in the 4 weeks after
   each US DST change: the evidence for the hybrid clock (chosen 2026-11-26).
4. The mid trap: share of |1-min return| >= 1 pip falling on minute :00, mid versus bid.
Writes results/vol_rv_daily.csv and results/vol_har_forecast_h{1,5}.csv.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from usdjpy import vol  # noqa: E402
from usdjpy.config import HOLDOUT_START, RESULTS_DIR  # noqa: E402
from usdjpy.datasets import load_minute  # noqa: E402

pd.set_option("display.width", 150, "display.float_format", "{:.3f}".format)
HOLD = pd.Timestamp(HOLDOUT_START, tz="UTC")


def us_dst_changes(years) -> pd.DatetimeIndex:
    """US DST change instants (UTC): 2nd Sunday of March 07:00, 1st Sunday of November 06:00."""
    out = []
    for y in years:
        m = pd.date_range(f"{y}-03-01", periods=31, freq="D", tz="UTC")
        n = pd.date_range(f"{y}-11-01", periods=30, freq="D", tz="UTC")
        out += [m[(m.month == 3) & (m.day_of_week == 6)][1] + pd.Timedelta("7h"),
                n[(n.month == 11) & (n.day_of_week == 6)][0] + pd.Timedelta("6h")]
    return pd.DatetimeIndex(out)


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    bars = load_minute("combined")
    bars = bars[bars.index < HOLD]

    print("=" * 78 + "\n1. Daily realised variance, 5-min bid, combined, pre-holdout\n" + "=" * 78)
    rv = vol.realized_variance(bars["bid"])
    rv = rv[rv.index < pd.Timestamp(HOLDOUT_START)]
    rv.to_csv(RESULTS_DIR / "vol_rv_daily.csv")
    wk = vol.weekday_series(rv["rv"])
    y = pd.DataFrame({
        "weekdays": wk.groupby(wk.index.year).size(),
        "valid": wk.notna().groupby(wk.index.year).sum(),
        "median_cov": rv["coverage"].groupby(rv.index.year).median(),
        "median_vol_ann": rv["rv"].groupby(rv.index.year).median().pipe(vol.annualise),
    })
    y["valid_share"] = y["valid"] / y["weekdays"]
    print(y.to_string())

    print("\n" + "=" * 78 + "\n2. HAR-RV out of sample (expanding window, refit daily)\n" + "=" * 78)
    for h in (1, 5):
        f = vol.har_forecast(rv["rv"], horizon=h)
        f.to_csv(RESULTS_DIR / f"vol_har_forecast_h{h}.csv")
        target = vol.har_target(wk, h)
        naive = wk.rolling(h, min_periods=max(1, int(np.ceil(0.8 * h)))).mean()
        d = pd.DataFrame({"har": f["forecast"], "naive": naive, "y": target}).dropna()
        mse = ((d.har - d.y) ** 2).mean() / ((d.naive - d.y) ** 2).mean()
        ql = lambda fc: (d.y / fc - np.log(d.y / fc) - 1).mean()  # noqa: E731
        last = f.dropna().iloc[-1]
        print(f"h={h}: n {len(d)}, first forecast {f['forecast'].first_valid_index().date()}, "
              f"MSE har/naive {mse:.3f}, QLIKE har {ql(d.har):.4f} naive {ql(d.naive):.4f}, "
              f"corr(har, realised) {np.corrcoef(d.har, d.y)[0, 1]:.3f}")
        print(f"     final coefficients: b0 {last.b0:.2e}, b1 {last.b_1:.3f}, b5 {last.b_5:.3f}, "
              f"b22 {last.b_22:.3f} (sum {last.b_1 + last.b_5 + last.b_22:.3f})")

    print("\n" + "=" * 78 + "\n3. Minute-of-week baseline coverage, HistData 2015-2024 1-min |bid return|\n" + "=" * 78)
    hd = load_minute("histdata")
    hd = hd[(hd.index >= pd.Timestamp("2015-01-01", tz="UTC")) & (hd.index < HOLD)]
    r = vol.minute_returns(hd["bid"]).abs().dropna()
    # 3b: at two real recurring events, the 4 weeks after each US DST change: how well the
    # event's cell knows it (event / neighbour baseline) and how often |r| > 5x baseline.
    changes = us_dst_changes(range(2015, 2025))
    since = pd.Series(r.index, index=r.index) - changes[np.clip(changes.searchsorted(r.index, "right") - 1, 0, None)]
    early = ((since >= pd.Timedelta(0)) & (since < pd.Timedelta(weeks=4))).to_numpy()
    et, jst = r.index.tz_convert("America/New_York"), r.index.tz_convert("Asia/Tokyo")
    events = {
        "Thu 08:30 ET (jobless claims)": ((et.day_of_week == 3) & (et.hour == 8) & (et.minute == 30),
                                          (et.day_of_week == 3) & (et.hour == 8) & et.minute.isin([20, 22, 24, 26, 34, 36, 38, 40])),
        "09:55 JST (Tokyo fix)": ((jst.day_of_week < 5) & (jst.hour == 9) & (jst.minute == 55),
                                  (jst.day_of_week < 5) & (jst.hour == 9) & jst.minute.isin([45, 47, 49, 51, 59])),
    }
    for clock in ("hybrid", "utc", "Asia/Tokyo", "America/New_York", "jst_nydst"):
        b = vol.seasonal_baseline(r, clock=clock)
        cov = b.notna().mean()
        months = vol.profile_coverage(b)
        print(f"{clock:17s} share of minutes with a baseline {cov:.3f}; worst month {months.min():.3f} "
              f"({months.idxmin()}); months below 0.9: {int((months < 0.9).sum())}")
        for name, (ev, nb) in events.items():
            e_m, n_m = ev & early, nb & early
            has = int(b[e_m].notna().sum())
            ratio = b[e_m].median() / b[n_m].median() if has else np.nan
            shock = (r[e_m] > 5 * b[e_m]).sum() / has if has else np.nan
            print(f"   weeks 0-4 after a US DST change, {name:30s}: event/neighbour baseline {ratio:5.2f}, "
                  f"|r| > 5x baseline on {shock:6.1%} of {has} event minutes")

    print("\n" + "=" * 78 + "\n4. The mid trap, HistData 2015-2024 (bid-only, synthetic ask)\n" + "=" * 78)
    mid = (hd["bid"] + hd["ask"]) / 2
    rb, rm = vol.minute_returns(hd["bid"]), vol.minute_returns(mid)
    both = rb.notna() & rm.notna()
    spur = ((rm - rb)[both] * hd["bid"].reindex(rb.index)[both] / 0.01)      # pips; exactly the spread step / 2
    jst = spur.index.tz_convert("Asia/Tokyo")
    by = spur.abs().groupby([jst.hour, jst.minute]).max()
    print("largest |mid return - bid return| (pips) by JST minute, top 4:")
    print(by.sort_values(ascending=False).head(4).to_string())
    worst = by.idxmax()
    bb = vol.seasonal_baseline(rb.abs().dropna(), clock="Asia/Tokyo")   # the step is fixed in JST
    bm = vol.seasonal_baseline(rm.abs().dropna(), clock="Asia/Tokyo")
    at = (jst.hour == worst[0]) & (jst.minute == worst[1])
    idx = spur.index[at]
    fb = (rb.abs().reindex(idx) > 5 * bb.reindex(idx)).mean()
    fm = (rm.abs().reindex(idx) > 5 * bm.reindex(idx)).mean()
    print(f"at {worst[0]:02d}:{worst[1]:02d} JST ({len(idx)} days): |r| > 5 x its baseline on "
          f"{fm:.1%} of days on the mid, {fb:.1%} on the bid")


if __name__ == "__main__":
    main()
