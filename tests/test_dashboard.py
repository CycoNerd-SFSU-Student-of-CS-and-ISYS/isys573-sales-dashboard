"""
Tests for ISYS 573 Sales Dashboard
===================================
Run: pytest tests/ -v
"""

import pytest
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from dashboard import load_data, build_region_bar, build_monthly_line, \
                      build_category_pie, build_top_products, build_html

DATA_PATH = Path(__file__).parent.parent / "data" / "sales.csv"


@pytest.fixture
def df() -> pd.DataFrame:
    return load_data(DATA_PATH)


class TestLoadData:
    def test_loads_without_error(self, df):
        assert len(df) == 500

    def test_required_columns_present(self, df):
        required = {"date", "region", "category", "product",
                    "units_sold", "unit_price", "revenue", "channel"}
        assert required.issubset(set(df.columns))

    def test_date_parsed_as_datetime(self, df):
        assert pd.api.types.is_datetime64_any_dtype(df["date"])

    def test_quarter_column_added(self, df):
        assert "quarter" in df.columns
        assert set(df["quarter"].unique()).issubset({"Q1", "Q2", "Q3", "Q4"})

    def test_month_column_added(self, df):
        assert "month" in df.columns

    def test_revenue_is_positive(self, df):
        assert (df["revenue"] > 0).all()

    def test_four_regions(self, df):
        assert df["region"].nunique() == 4

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_data(Path("/nonexistent/path.csv"))


class TestRegionChart:
    def test_returns_figure(self, df):
        fig = build_region_bar(df)
        assert fig is not None

    def test_has_four_bars(self, df):
        fig = build_region_bar(df)
        # single go.Bar trace; y-axis holds the 4 region labels
        assert len(fig.data) == 1
        assert len(fig.data[0].y) == 4

    def test_filtered_by_quarter(self, df):
        q1 = df[df["quarter"] == "Q1"]
        fig = build_region_bar(q1)
        # Should only show regions present in Q1
        assert len(fig.data[0].x) <= 4


class TestMonthlyChart:
    def test_returns_figure(self, df):
        fig = build_monthly_line(df)
        assert fig is not None

    def test_has_twelve_months_or_fewer(self, df):
        fig = build_monthly_line(df)
        assert len(fig.data[0].x) <= 12

    def test_revenue_values_are_positive(self, df):
        fig = build_monthly_line(df)
        assert all(v > 0 for v in fig.data[0].y)


class TestCategoryChart:
    def test_returns_figure(self, df):
        fig = build_category_pie(df)
        assert fig is not None

    def test_six_categories(self, df):
        fig = build_category_pie(df)
        assert len(fig.data[0].labels) == 6


class TestTopProducts:
    def test_returns_figure(self, df):
        fig = build_top_products(df)
        assert fig is not None

    def test_default_top_10(self, df):
        fig = build_top_products(df)
        assert len(fig.data[0].y) == 10

    def test_custom_n(self, df):
        fig = build_top_products(df, n=5)
        assert len(fig.data[0].y) == 5

    def test_sorted_ascending_for_horizontal_bar(self, df):
        fig = build_top_products(df)
        revenues = list(fig.data[0].x)
        assert revenues == sorted(revenues)


class TestChartValueTypes:
    """All chart value arrays must be plain Python sequences — no typed-array dicts."""

    def test_region_bar_x_is_plain_sequence(self, df):
        fig = build_region_bar(df)
        assert isinstance(fig.data[0].x, (list, tuple))
        assert all(isinstance(v, float) for v in fig.data[0].x)

    def test_region_bar_y_is_plain_sequence(self, df):
        fig = build_region_bar(df)
        assert isinstance(fig.data[0].y, (list, tuple))
        assert all(isinstance(v, str) for v in fig.data[0].y)

    def test_monthly_line_values_are_plain_sequences(self, df):
        fig = build_monthly_line(df)
        assert isinstance(fig.data[0].x, (list, tuple))
        assert isinstance(fig.data[0].y, (list, tuple))
        assert all(isinstance(v, float) for v in fig.data[0].y)

    def test_category_pie_values_are_plain_sequences(self, df):
        fig = build_category_pie(df)
        assert isinstance(fig.data[0].labels, (list, tuple))
        assert isinstance(fig.data[0].values, (list, tuple))
        assert all(isinstance(v, float) for v in fig.data[0].values)

    def test_top_products_values_are_plain_sequences(self, df):
        fig = build_top_products(df)
        assert isinstance(fig.data[0].x, (list, tuple))
        assert isinstance(fig.data[0].y, (list, tuple))
        assert all(isinstance(v, float) for v in fig.data[0].x)


class TestQuarterFiltering:
    """Chart values must differ between quarters when the underlying data differs."""

    @pytest.fixture
    def q1(self, df):
        return df[df["quarter"] == "Q1"]

    @pytest.fixture
    def q2(self, df):
        return df[df["quarter"] == "Q2"]

    def test_region_bar_revenues_differ_q1_vs_q2(self, q1, q2):
        revenues_q1 = sorted(build_region_bar(q1).data[0].x)
        revenues_q2 = sorted(build_region_bar(q2).data[0].x)
        assert revenues_q1 != revenues_q2

    def test_monthly_line_months_differ_q1_vs_q2(self, q1, q2):
        months_q1 = list(build_monthly_line(q1).data[0].x)
        months_q2 = list(build_monthly_line(q2).data[0].x)
        assert months_q1 != months_q2

    def test_category_pie_revenues_differ_q1_vs_q2(self, q1, q2):
        vals_q1 = sorted(build_category_pie(q1).data[0].values)
        vals_q2 = sorted(build_category_pie(q2).data[0].values)
        assert vals_q1 != vals_q2

    def test_top_products_revenues_differ_q1_vs_q2(self, q1, q2):
        x_q1 = list(build_top_products(q1).data[0].x)
        x_q2 = list(build_top_products(q2).data[0].x)
        assert x_q1 != x_q2

    def test_region_bar_matches_pandas_totals_q1(self, q1):
        fig = build_region_bar(q1)
        expected = (
            q1.groupby("region")["revenue"]
            .sum()
            .sort_values(ascending=True)
            .astype(float)
            .tolist()
        )
        assert list(fig.data[0].x) == pytest.approx(expected, rel=1e-6)

    def test_monthly_line_matches_pandas_totals_q1(self, q1):
        fig = build_monthly_line(q1)
        expected = (
            q1.groupby("month")["revenue"]
            .sum()
            .reset_index()
            .sort_values("month")["revenue"]
            .astype(float)
            .tolist()
        )
        assert list(fig.data[0].y) == pytest.approx(expected, rel=1e-6)


class TestBuildHtml:
    """Generated HTML must not contain stale CDN versions or typed-array payloads."""

    @pytest.fixture
    def html(self, df):
        return build_html(df)

    def test_no_stale_plotlyjs_2_27(self, html):
        assert "plotly-2.27.0.min.js" not in html

    def test_no_typed_array_dtype_marker(self, html):
        assert '"dtype"' not in html

    def test_no_typed_array_bdata_marker(self, html):
        assert '"bdata"' not in html

    def test_all_quarter_keys_present(self, html):
        for q in ("Full Year", "Q1", "Q2", "Q3", "Q4"):
            assert q in html

    def test_quarter_dropdown_present(self, html):
        assert 'id="qFilter"' in html
        assert "applyFilter" in html

    def test_kpi_total_revenue_format(self, df, html):
        total = df["revenue"].sum()
        expected = f"${total:,.0f}"
        assert expected in html
