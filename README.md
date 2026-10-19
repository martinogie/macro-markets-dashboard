# Macro & Markets Dashboard (live)

A markets and economy dashboard that keeps itself up to date, built twice: in **Tableau Public** and in
**Power BI**. A scheduled GitHub Actions job pulls 12 series from official public sources every weekday, cleans them, and commits fresh CSVs to this repo. Both dashboards read those files, so they show
the latest Treasury yields, Fed rate, inflation and market moves without anyone touching them.

```
Treasury, NY Fed, BLS, Cboe, EIA, ECB ──► GitHub Actions, 8:15am & 6:15pm CT weekdays ──► data/*.csv in this repo
                                                                            │
                                     Google Sheet (IMPORTDATA) ◄────────────┤
                                       │                                    │
                         Tableau Public (daily sync)          Power BI (Web connector, Refresh)
```

## What it tracks

| Group | Series | Source |
|---|---|---|
| Rates | 3-month, 2-year, 10-year, 30-year Treasury; 10y minus 2y spread | US Treasury daily par yield curve |
| Rates | Effective federal funds rate | Federal Reserve Bank of New York |
| Economy | CPI inflation, year over year (CPI-U, all items); unemployment rate | Bureau of Labor Statistics API |
| Markets | S&P 500 and VIX | Cboe daily index history |
| Markets | WTI crude oil, spot | U.S. Energy Information Administration |
| Markets | US$ per euro | European Central Bank reference rate |
| Yield curve | 1 month to 30 years, today vs 1 month ago vs 1 year ago | US Treasury |

## Data files (refreshed automatically)

| File | Contents | Link for Tableau / Power BI |
|---|---|---|
| `series_long.csv` | one row per date and series, daily from 2019 and monthly for the last 10 years | [raw](https://raw.githubusercontent.com/martinogie/macro-markets-dashboard/main/data/series_long.csv) |
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
needs no API keys, and can be started by hand from the Actions tab (**Run workflow**).

## Data note

Sources: U.S. Department of the Treasury, Federal Reserve Bank of New York, U.S. Bureau of Labor Statistics, Cboe Global
Markets, U.S. Energy Information Administration and the European Central Bank. Built with AI-assisted coding (Claude); the series choice, design and review are my own.
