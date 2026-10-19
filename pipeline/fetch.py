"""Pull markets and economy series from FRED and write tidy CSVs for Tableau and Power BI.

Runs every weekday on GitHub Actions (see .github/workflows/refresh.yml). No API key needed: it uses
FRED's public CSV download (fredgraph.csv).

Outputs in data/:
  series_long.csv   one row per date and series (daily series from 2019, monthly series from 2015)
  kpis.csv          latest value per series with 1-day, 1-month and 1-year changes
  yield_curve.csv   Treasury curve today, 1 month ago and 1 year ago
  refreshed.csv     timestamp of the last successful run
"""
import io
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "data"
URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"

# id: (name, category, unit, frequency)
SERIES = {
    "DFF": ("Fed funds rate", "Rates", "%", "D"),
    "DGS3MO": ("3-month Treasury", "Rates", "%", "D"),
    "DGS2": ("2-year Treasury", "Rates", "%", "D"),
    "DGS10": ("10-year Treasury", "Rates", "%", "D"),
    "DGS30": ("30-year Treasury", "Rates", "%", "D"),
    "T10Y2Y": ("10y minus 2y spread", "Rates", "pp", "D"),
    "MORTGAGE30US": ("30-year mortgage rate", "Rates", "%", "W"),
    "SP500": ("S&P 500", "Markets", "index", "D"),
    "VIXCLS": ("VIX volatility", "Markets", "index", "D"),
    "DCOILWTICO": ("WTI crude oil", "Markets", "$/bbl", "D"),
    "DEXUSEU": ("US$ per euro", "Markets", "$", "D"),
    "CPIAUCSL": ("CPI index", "Economy", "index", "M"),
    "UNRATE": ("Unemployment rate", "Economy", "%", "M"),
}
CURVE = {"DGS1MO": 1 / 12, "DGS3MO": 0.25, "DGS6MO": 0.5, "DGS1": 1, "DGS2": 2, "DGS3": 3,
         "DGS5": 5, "DGS7": 7, "DGS10": 10, "DGS20": 20, "DGS30": 30}
DAILY_START, MONTHLY_START = "2019-01-01", "2015-01-01"


def fetch(series_id, tries=4):
    for attempt in range(tries):
        try:
            req = Request(URL.format(series_id), headers={"User-Agent": "macro-markets-dashboard"})
            text = urlopen(req, timeout=60).read().decode()
            df = pd.read_csv(io.StringIO(text))
            df.columns = ["date", "value"]
            df["date"] = pd.to_datetime(df["date"])
            df["value"] = pd.to_numeric(df["value"], errors="coerce")  # FRED marks gaps as "." or blank
            return df.dropna()
        except Exception as e:  # network hiccup: back off and retry
            print(f"{series_id}: attempt {attempt + 1} failed: {e}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"could not fetch {series_id}")


def change_at(s, latest_date, days):
    """Value change versus the last observation on or before latest_date - days."""
    prior = s[s.index <= latest_date - pd.Timedelta(days=days)]
    return s.iloc[-1] - prior.iloc[-1] if len(prior) else None


def main():
    OUT.mkdir(exist_ok=True)
    frames, kpis = [], []
    raw = {}
    for sid in sorted(set(SERIES) | set(CURVE)):
        raw[sid] = fetch(sid)

    for sid, (name, cat, unit, freq) in SERIES.items():
        df = raw[sid].copy()
        if sid == "CPIAUCSL":  # report inflation as year-over-year %
            df["value"] = (df["value"] / df["value"].shift(12) - 1) * 100
            name, unit, sid_out = "CPI inflation (YoY)", "%", "CPI_YOY"
            df = df.dropna()
        else:
            sid_out = sid
        start = MONTHLY_START if freq == "M" else DAILY_START
        df = df[df["date"] >= start]
        df = df.assign(series_id=sid_out, series=name, category=cat, unit=unit, frequency=freq)
        frames.append(df)

        s = df.set_index("date")["value"]
        last = s.index[-1]
        kpis.append({
            "series_id": sid_out, "series": name, "category": cat, "unit": unit,
            "as_of": last.date().isoformat(), "value": round(s.iloc[-1], 4),
            "chg_1d": None if freq != "D" else round(s.iloc[-1] - s.iloc[-2], 4),
            "chg_1m": change_at(s, last, 30), "chg_1y": change_at(s, last, 365),
        })

    long = pd.concat(frames)[["date", "series_id", "series", "category", "unit", "frequency", "value"]]
    long["value"] = long["value"].round(4)
    long.sort_values(["series_id", "date"]).to_csv(OUT / "series_long.csv", index=False, date_format="%Y-%m-%d")

    k = pd.DataFrame(kpis)
    for c in ("chg_1m", "chg_1y"):
        k[c] = pd.to_numeric(k[c]).round(4)
    k.to_csv(OUT / "kpis.csv", index=False)

    curve_rows = []
    latest = min(raw[s]["date"].max() for s in CURVE)
    for label, days in (("Today", 0), ("1 month ago", 30), ("1 year ago", 365)):
        when = latest - pd.Timedelta(days=days)
        for sid, years in CURVE.items():
            d = raw[sid][raw[sid]["date"] <= when].iloc[-1]
            curve_rows.append({"snapshot": label, "as_of": d["date"].date().isoformat(), "tenor": sid.replace("DGS", ""),
                               "years": round(years, 4), "yield": d["value"]})
    pd.DataFrame(curve_rows).to_csv(OUT / "yield_curve.csv", index=False)

    pd.DataFrame([{"refreshed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
                   "latest_market_date": latest.date().isoformat(), "rows": len(long)}]).to_csv(OUT / "refreshed.csv", index=False)
    print(f"wrote {len(long):,} rows; latest market date {latest.date()}")


if __name__ == "__main__":
    main()
