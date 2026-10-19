# Macro & Markets Dashboard (live)

A markets and economy dashboard that keeps itself up to date, built twice: in **Tableau Public** and in
**Power BI**. A scheduled GitHub Actions job pulls 13 series from the Federal Reserve's FRED database every
weekday, cleans them, and commits fresh CSVs to this repo. Both dashboards read those files, so they show
the latest Treasury yields, Fed rate, inflation and market moves without anyone touching them.

```
FRED (Federal Reserve) ──► GitHub Actions, 8:15am & 6:15pm CT weekdays ──► data/*.csv in this repo
                                                                            │
                                     Google Sheet (IMPORTDATA) ◄────────────┤
                                       │                                    │
                         Tableau Public (daily sync)          Power BI (Web connector, Refresh)
```

## What it tracks

| Group | Series (FRED id) |
|---|---|
| Rates | Fed funds (DFF), 3-month (DGS3MO), 2-year (DGS2), 10-year (DGS10) and 30-year (DGS30) Treasury, 10y–2y spread (T10Y2Y), 30-year mortgage (MORTGAGE30US) |
| Markets | S&P 500 (SP500), VIX (VIXCLS), WTI crude (DCOILWTICO), US$ per euro (DEXUSEU) |
| Economy | CPI inflation, year over year (from CPIAUCSL), unemployment rate (UNRATE) |
| Yield curve | 1 month to 30 years, today vs 1 month ago vs 1 year ago |

## Data files (refreshed automatically)

| File | Contents | Link for Tableau / Power BI |
|---|---|---|
| `series_long.csv` | one row per date and series, daily from 2019 and monthly from 2015 | [raw](https://raw.githubusercontent.com/martinogie/macro-markets-dashboard/main/data/series_long.csv) |
| `kpis.csv` | latest value with 1-day, 1-month and 1-year change | [raw](https://raw.githubusercontent.com/martinogie/macro-markets-dashboard/main/data/kpis.csv) |
| `yield_curve.csv` | Treasury curve snapshots | [raw](https://raw.githubusercontent.com/martinogie/macro-markets-dashboard/main/data/yield_curve.csv) |
| `refreshed.csv` | time of the last successful run | [raw](https://raw.githubusercontent.com/martinogie/macro-markets-dashboard/main/data/refreshed.csv) |

## How each tool stays live

- **Power BI**: the report connects to the raw CSV links with the Web connector (see `powerbi/queries.pq`).
  Clicking **Refresh** pulls the latest run. Scheduled refresh in the Power BI service needs a work account.
- **Tableau Public**: Tableau Public can refresh on a schedule only from Google Sheets, so a Google Sheet
  pulls the CSVs with `IMPORTDATA`, and the Tableau workbook has **Keep this data in sync** turned on, which
  refreshes it once a day.

## Run the pipeline yourself

```bash
pip install pandas
python pipeline/fetch.py     # writes data/*.csv
```

The workflow (`.github/workflows/refresh.yml`) runs the same script, commits only when the data changed,
and can be started by hand from the Actions tab (**Run workflow**).

## Data note

Source: Federal Reserve Bank of St. Louis, FRED. Series are public; ICE and S&P data on FRED carry their
providers' terms of use. Built with AI-assisted coding (Claude); the series choice, design and review are my own.
