# Bug: Dashboard charts render dummy values after Plotly.py 6 upgrade

## Summary

The generated `dashboard.html` is not rendering the actual revenue values from
`data/sales.csv`. The labels change when the quarter filter changes, and the KPI
cards appear to update, but the charts themselves look like they are using
dummy or index-like values:

- Every quarter view has nearly identical chart geometry.
- Bar lengths do not reflect the real revenue totals.
- The donut chart shows equal or near-equal slices even when category revenue is
  not equal.
- The monthly line chart appears to use small sequential values instead of
  actual monthly revenue.

This makes the dashboard misleading because the browser is not displaying the
numeric values calculated by Pandas.

## Repo Context

This work is happening on a fork:

- `origin`: `https://github.com/CycoNerd-SFSU-Student-of-CS-and-ISYS/isys573-sales-dashboard.git`
- `upstream`: `https://github.com/samgill172/isys573-sales-dashboard`
- Branch: `main`

The current dependency set pins newer packages, including:

- `plotly==6.7.0`
- `pandas==3.0.3`
- `numpy==2.4.5`

However, `dashboard.py` still hardcodes an old Plotly.js bundle:

```html
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
```

## Evidence

The generated `dashboard.html` contains Plotly.py 6 typed-array payloads such as:

```json
{"dtype":"f8","bdata":"..."}
```

Those payloads appear inside chart fields such as `x`, `y`, `values`, and marker
colors. At the same time, the page loads Plotly.js `2.27.0`, which is hardcoded
in the HTML template.

Plotly's own migration documentation for version 6 says Plotly.py now uses
recent Plotly.js typed-array handling for NumPy and NumPy-convertible arrays:

https://plotly.com/python/v6-migration/

Plotly's HTML export documentation also says `include_plotlyjs="cdn"` uses a
versioned CDN URL that matches the bundled Plotly.js version:

https://plotly.com/python-api-reference/generated/plotly.io.html

## Suspected Root Cause

`dashboard.py` builds charts directly from Pandas Series and grouped DataFrame
columns, then serializes each figure with `fig.to_json()`. With Plotly.py 6,
NumPy/Pandas-style numeric arrays can serialize as typed-array objects using
`dtype` and `bdata`.

The custom HTML then manually loads an obsolete Plotly.js CDN script. That older
browser-side Plotly.js code does not match the Plotly.py 6 JSON payload shape, so
labels can still appear while numeric arrays render incorrectly.

This is probably why the chart labels change by filter, but the numeric geometry
does not.

## Suggested Fix

Do not pass Pandas Series, Indexes, or NumPy-backed arrays directly into Plotly
trace values for this dashboard. Convert all chart inputs to ordinary Python
lists before creating each figure.

Examples of the intended approach:

```python
x=summary["revenue"].astype(float).tolist()
y=summary["region"].astype(str).tolist()
values=cat["revenue"].astype(float).tolist()
labels=cat["category"].astype(str).tolist()
```

Apply this to every chart builder:

- `build_region_bar`
- `build_monthly_line`
- `build_category_pie`
- `build_top_products`

Also remove the hardcoded Plotly.js `2.27.0` script tag. The generator should use
the Plotly package installed in the environment to choose the matching Plotly.js
bundle.

Acceptable implementation directions:

- For a fully self-contained offline report, embed the bundled Plotly.js using
  Plotly's HTML export path, such as `include_plotlyjs=True`.
- If a CDN is intentionally kept, generate or derive the CDN script from Plotly's
  own HTML export behavior, such as `include_plotlyjs="cdn"`, so the URL matches
  the installed Plotly.py version instead of hardcoding an obsolete version.
- Preserve the project boundary that the output remains a single HTML report and
  no web server is added.
- Do not modify `data/sales.csv`.

The inline CSS/JS can remain in the single output file for now, but the generated
HTML should not hardcode stale dependency versions or embed chart JSON that the
loaded Plotly.js cannot understand.

## Acceptance Criteria

- `python dashboard.py` generates a working `dashboard.html`.
- The generated HTML no longer references `plotly-2.27.0.min.js`.
- The generated chart JSON uses ordinary numeric arrays for chart values instead
  of typed-array objects like `{"dtype":"f8","bdata":"..."}`.
- Full Year chart values match Pandas aggregations from `data/sales.csv`.
- Q1, Q2, Q3, and Q4 chart values each match Pandas aggregations for that quarter.
- Quarter filtering changes both labels and numeric chart geometry.
- The donut chart slice sizes reflect actual category revenue shares.
- The regional and product bar chart lengths reflect actual revenue totals.
- The monthly line chart uses actual monthly revenue totals, not sequential dummy
  values.
- KPI cards continue to show correctly formatted monetary values like `$2,090,224`
  with no decimals.
- The quarter dropdown functionality is preserved.
- The output remains a single HTML file with no Flask, FastAPI, Streamlit, or
  other web server dependency.
- `data/sales.csv` remains unchanged.

## Required Tests

Add or update pytest coverage in `tests/test_dashboard.py`.

Data and chart serialization tests:

- Test that every chart builder returns value arrays that can be converted to
  normal Python lists and match Pandas-calculated totals.
- Test `build_region_bar(df)` x-values equal `df.groupby("region")["revenue"].sum()`
  after applying the chart's sort order.
- Test `build_monthly_line(df)` y-values equal monthly revenue sums for all months
  after applying the chart's sort order.
- Test `build_category_pie(df)` values equal category revenue sums.
- Test `build_top_products(df)` x-values equal the top N product revenue sums
  after applying the chart's sort order.
- Test each builder with a quarter-filtered subset, not just the full dataset.

Generated HTML tests:

- Test `build_html(df)` does not contain `plotly-2.27.0.min.js`.
- Test `build_html(df)` does not emit typed-array chart payload markers such as
  `"dtype"` and `"bdata"` for chart values.
- Test `build_html(df)` includes all quarter keys: `Full Year`, `Q1`, `Q2`,
  `Q3`, and `Q4`.
- Test the generated HTML still contains the quarter filter dropdown and calls
  the filter handler for all quarter options.
- Test KPI values in the generated HTML match Pandas totals for each quarter and
  use `$x,xxx` formatting with no decimals.

End-to-end/manual verification:

- Run `python dashboard.py`.
- Open `dashboard.html` directly from disk.
- Verify Full Year, Q1, Q2, Q3, and Q4 each show visibly different chart geometry
  where the underlying data differs.
- Verify chart hover values match the expected Pandas aggregation results.
- Run `pytest tests/ -v` before opening the PR.

## Maintainer Note

The current custom JavaScript and dependency hardcoding are brittle enough that
the Copilot-generated path should be treated as discarded. In local project
terms: Copilot was trash, the garbage collector came and took it away, and Codex
is on the job doing the cleanup after the Cukoopilot dumpster fire.
