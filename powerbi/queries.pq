// Power BI: Home > Transform data > New source > Blank query > Advanced editor, paste one query each.
// Base URL of the auto-refreshed files
// Query: SeriesLong
let
    Source = Csv.Document(Web.Contents("https://raw.githubusercontent.com/martinogie/macro-markets-dashboard/main/data/series_long.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {{"date", type date}, {"value", type number}}, "en-US")
in
    Typed

// Query: KPIs
let
    Source = Csv.Document(Web.Contents("https://raw.githubusercontent.com/martinogie/macro-markets-dashboard/main/data/kpis.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {{"as_of", type date}, {"value", type number}, {"chg_1d", type number}, {"chg_1m", type number}, {"chg_1y", type number}}, "en-US")
in
    Typed

// Query: YieldCurve
let
    Source = Csv.Document(Web.Contents("https://raw.githubusercontent.com/martinogie/macro-markets-dashboard/main/data/yield_curve.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {{"as_of", type date}, {"years", type number}, {"yield", type number}}, "en-US")
in
    Typed
