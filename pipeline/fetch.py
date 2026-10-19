"""Pull markets and economy data from official public sources and write tidy CSVs for Tableau and Power BI.

Runs every weekday on GitHub Actions (see .github/workflows/refresh.yml). No API keys needed:

  US Treasury     daily par yield curve (1 month to 30 years)       home.treasury.gov
  New York Fed    effective federal funds rate                       markets.newyorkfed.org
  BLS             CPI (all items, NSA) and unemployment rate         api.bls.gov (public v1 API)
  Yahoo Finance   S&P 500, VIX, WTI crude futures, euro/dollar       query1.finance.yahoo.com

Outputs in data/:
  series_long.csv   one row per date and series (daily series from 2019, monthly from 2016)
  kpis.csv          latest value per series with 1-day, 1-month and 1-year changes
  yield_curve.csv   Treasury curve today, 1 month ago and 1 year ago
  refreshed.csv     time of the last successful run and any source that failed
"""
import io
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "data"
START_YEAR = 2019
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
TODAY = date.today()

TREASURY = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/"
            "{year}/all?type=daily_treasury_yield_curve&field_tdr_date_value={year}&page&_format=csv")
NYFED = "https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json?startDate={start}&endDate={end}"
BLS = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval=1d"

TENORS = {"1 Mo": ("1MO", 1 / 12), "3 Mo": ("3MO", 0.25), "6 Mo": ("6MO", 0.5), "1 Yr": ("1", 1), "2 Yr": ("2", 2),
          "3 Yr": ("3", 3), "5 Yr": ("5", 5), "7 Yr": ("7", 7), "10 Yr": ("10", 10), "20 Yr": ("20", 20),
          "30 Yr": ("30", 30)}
# series_id: (name, category, unit, frequency)
META = {
    "FEDFUNDS": ("Fed funds rate (effective)", "Rates", "%", "D"),
    "UST3M": ("3-month Treasury", "Rates", "%", "D"),
    "UST2Y": ("2-year Treasury", "Rates", "%", "D"),
    "UST10Y": ("10-year Treasury", "Rates", "%", "D"),
    "UST30Y": ("30-year Treasury", "Rates", "%", "D"),
    "SPREAD_10Y2Y": ("10y minus 2y spread", "Rates", "pp", "D"),
    "SP500": ("S&P 500", "Markets", "index", "D"),
    "VIX": ("VIX volatility", "Markets", "index", "D"),
    "WTI": ("WTI crude oil (front month)", "Markets", "$/bbl", "D"),
    "EURUSD": ("US$ per euro", "Markets", "$", "D"),
    "CPI_YOY": ("CPI inflation (YoY)", "Economy", "%", "M"),
    "UNRATE": ("Unemployment rate", "Economy", "%", "M"),
}


def get(url, data=None, tries=3, timeout=40):
    for attempt in range(tries):
        try:
            headers = dict(UA, **({"Content-Type": "application/json"} if data else {}))
            return urlopen(Request(url, data=data, headers=headers), timeout=timeout).read()
        except Exception as e:
            print(f"  attempt {attempt + 1} failed for {url[:90]}: {e}", file=sys.stderr)
            time.sleep(4 * (attempt + 1))
    raise RuntimeError(f"giving up on {url[:90]}")


def treasury():
    frames = []
    for year in range(START_YEAR - 1, TODAY.year + 1):  # one extra year so the 1-year-ago curve exists
        frames.append(pd.read_csv(io.BytesIO(get(TREASURY.format(year=year)))))
    df = pd.concat(frames)
    df["Date"] = pd.to_datetime(df["Date"])
    return df.sort_values("Date")


def nyfed():
    url = NYFED.format(start=f"{START_YEAR}-01-01", end=TODAY.isoformat())
    rows = json.loads(get(url))["refRates"]
    df = pd.DataFrame(rows)[["effectiveDate", "percentRate"]]
    return pd.DataFrame({"date": pd.to_datetime(df["effectiveDate"]), "value": df["percentRate"].astype(float)})


def bls():
    out = {}
    for start, end in ((TODAY.year - 10, TODAY.year - 1), (TODAY.year - 1, TODAY.year)):  # v1 allows 10 years a call
        body = json.dumps({"seriesid": ["CUUR0000SA0", "LNS14000000"], "startyear": str(start), "endyear": str(end)})
        res = json.loads(get(BLS, data=body.encode()))
        if res.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError(f"BLS: {res.get('message')}")
        for s in res["Results"]["series"]:
            for d in s["data"]:
                if d["period"].startswith("M") and d["period"] != "M13" and d["value"] not in ("-", ""):
                    key = (s["seriesID"], pd.Timestamp(int(d["year"]), int(d["period"][1:]), 1))
                    out[key] = float(d["value"])
    df = pd.DataFrame([(k[0], k[1], v) for k, v in out.items()], columns=["sid", "date", "value"]).sort_values("date")
    cpi = df[df["sid"] == "CUUR0000SA0"].set_index("date")["value"]
    cpi_yoy = ((cpi / cpi.shift(12) - 1) * 100).dropna()
    unrate = df[df["sid"] == "LNS14000000"].set_index("date")["value"]
    return cpi_yoy, unrate


def yahoo(symbol):
    p1 = int(datetime(START_YEAR - 1, 1, 1, tzinfo=timezone.utc).timestamp())
    p2 = int(datetime.now(timezone.utc).timestamp())
    res = json.loads(get(YAHOO.format(sym=symbol.replace("^", "%5E").replace("=", "%3D"), p1=p1, p2=p2)))["chart"]["result"][0]
    s = pd.Series(res["indicators"]["quote"][0]["close"], index=pd.to_datetime(res["timestamp"], unit="s").normalize())
    return s.dropna().groupby(level=0).last()


def change_at(s, last, days):
    prior = s[s.index <= last - pd.Timedelta(days=days)]
    return round(s.iloc[-1] - prior.iloc[-1], 4) if len(prior) else None


def main():
    OUT.mkdir(exist_ok=True)
    series, failed = {}, []

    def attempt(name, fn):
        print(f"fetching {name}")
        try:
            return fn()
        except Exception as e:
            print(f"{name} FAILED: {e}", file=sys.stderr)
            failed.append(name)
            return None

    ust = attempt("Treasury yield curve", treasury)
    if ust is not None:
        ix = ust.set_index("Date")
        for col, sid in (("3 Mo", "UST3M"), ("2 Yr", "UST2Y"), ("10 Yr", "UST10Y"), ("30 Yr", "UST30Y")):
            series[sid] = ix[col].dropna()
        series["SPREAD_10Y2Y"] = (ix["10 Yr"] - ix["2 Yr"]).dropna()

    ff = attempt("Fed funds (NY Fed)", nyfed)
    if ff is not None:
        series["FEDFUNDS"] = ff.set_index("date")["value"].sort_index()

    b = attempt("CPI and unemployment (BLS)", bls)
    if b is not None:
        series["CPI_YOY"], series["UNRATE"] = b

    for sid, sym in (("SP500", "^GSPC"), ("VIX", "^VIX"), ("WTI", "CL=F"), ("EURUSD", "EURUSD=X")):
        s = attempt(f"{sid} (Yahoo)", lambda sym=sym: yahoo(sym))
        if s is not None:
            series[sid] = s

    if len(series) < 6:
        raise SystemExit(f"only {len(series)} series fetched ({failed} failed); keeping the previous data")

    frames, kpis = [], []
    for sid, s in series.items():
        name, cat, unit, freq = META[sid]
        s = s[s.index >= (f"{START_YEAR}-01-01" if freq == "D" else f"{TODAY.year - 9}-01-01")].round(4)
        frames.append(pd.DataFrame({"date": s.index, "series_id": sid, "series": name, "category": cat,
                                    "unit": unit, "frequency": freq, "value": s.values}))
        last = s.index[-1]
        kpis.append({"series_id": sid, "series": name, "category": cat, "unit": unit,
                     "as_of": last.date().isoformat(), "value": s.iloc[-1],
                     "chg_1d": round(s.iloc[-1] - s.iloc[-2], 4) if freq == "D" else None,
                     "chg_1m": change_at(s, last, 30), "chg_1y": change_at(s, last, 365)})

    long = pd.concat(frames).sort_values(["series_id", "date"])
    long.to_csv(OUT / "series_long.csv", index=False, date_format="%Y-%m-%d")
    pd.DataFrame(kpis).to_csv(OUT / "kpis.csv", index=False)

    latest_market = max(s.index[-1] for k, s in series.items() if META[k][3] == "D")
    if ust is not None:
        ix = ust.set_index("Date")
        rows = []
        for label, days in (("Today", 0), ("1 month ago", 30), ("1 year ago", 365)):
            row = ix[ix.index <= ix.index[-1] - pd.Timedelta(days=days)].iloc[-1]
            for col, (tenor, years) in TENORS.items():
                if col in row and pd.notna(row[col]):
                    rows.append({"snapshot": label, "as_of": row.name.date().isoformat(), "tenor": tenor,
                                 "years": round(years, 4), "yield": row[col]})
        pd.DataFrame(rows).to_csv(OUT / "yield_curve.csv", index=False)

    pd.DataFrame([{"refreshed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
                   "latest_market_date": latest_market.date().isoformat(), "rows": len(long),
                   "failed_sources": "; ".join(failed)}]).to_csv(OUT / "refreshed.csv", index=False)
    print(f"wrote {len(long):,} rows across {len(series)} series; latest market date {latest_market.date()}")


if __name__ == "__main__":
    main()
