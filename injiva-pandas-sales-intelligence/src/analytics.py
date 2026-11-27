"""
analytics.py
============
STAGES 4 to 9: financial transformation, sales performance, time series,
segmentation, multi-DataFrame operations and business intelligence.

METRIC DEFINITIONS (decided BEFORE calculating, as the brief asks)
------------------------------------------------------------------
Gross_Revenue        = Quantity * Unit_Price             (before discount)
Discount_Amount      = Gross_Revenue * Discount_Percent / 100
Net_Revenue          = Gross_Revenue - Discount_Amount   ("revenue" in reports)
Total_Cost           = Quantity * Unit_Cost
Gross_Profit         = Net_Revenue - Total_Cost
Gross_Profit_Margin  = Gross_Profit / Net_Revenue * 100  (NaN if Net_Revenue = 0)
Overall margin       = SUM(Gross_Profit) / SUM(Net_Revenue) * 100
                       (NOT the average of transaction margins)
Average transaction value = SUM(Net_Revenue) / number of valid transactions

Gross profit is not NET profit: rent, salaries and other overheads are
not in the data, so net profit cannot be calculated.

TIED RANKINGS: ranks use ``method="min"`` (for example 1, 2, 2, 4), so
tied items share the better rank and the next rank is skipped.
"""

import re

import numpy as np
import pandas as pd

from src.source_data import COMPANY_CITIES

# Tolerance for comparing money amounts. Floating-point arithmetic can
# give tiny differences such as 0.1 + 0.2 = 0.30000000000000004.
MONEY_TOLERANCE = 0.01


# ===========================================================================
# STAGE 4: FINANCIAL DATA TRANSFORMATION
# ===========================================================================
def safe_margin(profit, revenue):
    """Profit margin in percent that never divides by zero.

    ``np.where`` picks, element by element: the real margin where revenue
    is not zero, and NaN (meaning "not defined") where it is zero.
    Inputs can be single numbers or whole columns.
    """
    profit = np.asarray(profit, dtype="float64")
    revenue = np.asarray(revenue, dtype="float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        margin = np.where(revenue != 0, profit / revenue * 100, np.nan)
    return margin if margin.ndim else float(margin)


def add_financial_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add the six calculated financial columns (vectorised, no loops).

    Nothing is rounded here. Rounding intermediate values builds up
    small errors, so we only round when displaying results.
    """
    result = df.copy()
    result["Gross_Revenue"] = result["Quantity"] * result["Unit_Price"]
    # Divide by 100: 5 (percent) must become 0.05 (decimal).
    result["Discount_Amount"] = result["Gross_Revenue"] * (result["Discount_Percent"] / 100)
    result["Net_Revenue"] = result["Gross_Revenue"] - result["Discount_Amount"]
    result["Total_Cost"] = result["Quantity"] * result["Unit_Cost"]
    # Profit is calculated AFTER the discount (from Net_Revenue).
    result["Gross_Profit"] = result["Net_Revenue"] - result["Total_Cost"]
    result["Gross_Profit_Margin"] = safe_margin(result["Gross_Profit"], result["Net_Revenue"])
    return result


def verify_financial_calculations(df: pd.DataFrame) -> bool:
    """Recalculate the financial columns a DIFFERENT way and compare.

    Here net revenue is Q * P * (1 - d/100), a different but equivalent
    formula. If both methods agree, a typo in one formula is unlikely.
    Raises ValueError if any value differs by more than the tolerance.
    """
    alt_net = df["Quantity"] * df["Unit_Price"] * (1 - df["Discount_Percent"] / 100)
    alt_profit = alt_net - df["Quantity"] * df["Unit_Cost"]
    checks = {
        "Net_Revenue": np.isclose(df["Net_Revenue"], alt_net, atol=MONEY_TOLERANCE),
        "Gross_Profit": np.isclose(df["Gross_Profit"], alt_profit, atol=MONEY_TOLERANCE),
        "Discount_Amount": np.isclose(df["Discount_Amount"],
                                      df["Gross_Revenue"] - df["Net_Revenue"], atol=MONEY_TOLERANCE),
        "Discount not above gross": (df["Discount_Amount"] <= df["Gross_Revenue"] + MONEY_TOLERANCE).to_numpy(),
    }
    failures = [name for name, ok in checks.items() if not ok.all()]
    if failures:
        raise ValueError(f"Financial verification failed for: {failures}")
    return True


def loss_making_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """Transactions with negative gross profit (Boolean indexing)."""
    return df.loc[df["Gross_Profit"] < 0]


def financial_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Company-level financial totals as a two-column table."""
    total_net = df["Net_Revenue"].sum()
    total_profit = df["Gross_Profit"].sum()
    n_transactions = len(df)
    metrics = {
        "Valid transactions": n_transactions,
        "Total units sold": int(df["Quantity"].sum()),
        "Total gross revenue (USD)": df["Gross_Revenue"].sum(),
        "Total discount amount (USD)": df["Discount_Amount"].sum(),
        "Total net revenue (USD)": total_net,
        "Total cost (USD)": df["Total_Cost"].sum(),
        "Total gross profit (USD)": total_profit,
        # Overall margin = total profit / total revenue (NOT a mean of margins).
        "Overall gross profit margin (%)": safe_margin(total_profit, total_net),
        "Average transaction value (USD)": total_net / n_transactions if n_transactions else np.nan,
        "Loss-making transactions": len(loss_making_transactions(df)),
    }
    # Counts stay whole numbers; money and percentages are rounded to
    # 2 decimals ONLY here, for display. All calculations above used
    # full precision. dtype=object stops pandas turning 17 into 17.0.
    values = [int(v) if isinstance(v, (int, np.integer)) else round(float(v), 2)
              for v in metrics.values()]
    return pd.DataFrame({"Metric": list(metrics.keys()),
                         "Value": pd.Series(values, dtype=object)})


# ===========================================================================
# STAGE 5: SALES PERFORMANCE ANALYSIS
# ===========================================================================
def _performance_by(df: pd.DataFrame, key: str) -> pd.DataFrame:
    """Shared helper: aggregate the main metrics for any grouping column.

    ``groupby().agg()`` with named aggregations gives one row per group
    with clearly named columns. The same rules are used for products,
    cities and salespeople, so their results can be compared.
    """
    grouped = df.groupby(key).agg(
        Transactions=("Transaction_ID", "count"),
        Units_Sold=("Quantity", "sum"),
        Gross_Revenue=("Gross_Revenue", "sum"),
        Discount_Amount=("Discount_Amount", "sum"),
        Net_Revenue=("Net_Revenue", "sum"),
        Total_Cost=("Total_Cost", "sum"),
        Gross_Profit=("Gross_Profit", "sum"),
        Avg_Discount_Percent=("Discount_Percent", "mean"),
    )
    grouped["Gross_Profit_Margin"] = safe_margin(grouped["Gross_Profit"], grouped["Net_Revenue"])
    grouped["Revenue_Share_Percent"] = grouped["Net_Revenue"] / grouped["Net_Revenue"].sum() * 100
    grouped["Profit_Share_Percent"] = grouped["Gross_Profit"] / grouped["Gross_Profit"].sum() * 100
    # rank(): 1 = best. method="min" handles ties (see module docstring).
    grouped["Revenue_Rank"] = grouped["Net_Revenue"].rank(ascending=False, method="min").astype(int)
    grouped["Profit_Rank"] = grouped["Gross_Profit"].rank(ascending=False, method="min").astype(int)
    return grouped.sort_values("Net_Revenue", ascending=False)


def product_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Product metrics plus a flag for below-average margin."""
    result = _performance_by(df, "Product")
    overall_margin = safe_margin(df["Gross_Profit"].sum(), df["Net_Revenue"].sum())
    result["Below_Average_Margin"] = result["Gross_Profit_Margin"] < overall_margin
    return result


def category_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Category metrics, including volume and average discount."""
    return _performance_by(df, "Category")


def city_performance(df: pd.DataFrame, all_cities=COMPANY_CITIES) -> pd.DataFrame:
    """City metrics, including cities with NO records in the sample.

    Masvingo is shown with empty (NaN) metrics and a Data_Status note
    rather than zeros. Zero would claim "no sales happened", which the
    data cannot prove.
    """
    result = _performance_by(df, "City")
    result = result.reindex(list(result.index) + [c for c in all_cities if c not in result.index])
    # Reindexing adds NaN, which turns whole-number columns into floats.
    # "Int64" (capital I) is pandas' integer type that allows missing values.
    for column in ["Transactions", "Units_Sold", "Revenue_Rank", "Profit_Rank"]:
        result[column] = result[column].astype("Int64")
    result["Data_Status"] = np.where(result["Transactions"].notna(),
                                     "Records present", "No records in sample - activity unknown")
    result.index.name = "City"
    return result


def salesperson_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Salesperson metrics compared with the average salesperson."""
    result = _performance_by(df, "Salesperson")
    avg_revenue = result["Net_Revenue"].mean()
    avg_profit = result["Gross_Profit"].mean()
    result["Revenue_vs_Average"] = np.where(result["Net_Revenue"] >= avg_revenue, "At/above average", "Below average")
    result["Profit_vs_Average"] = np.where(result["Gross_Profit"] >= avg_profit, "At/above average", "Below average")
    return result


def payment_method_summary(df: pd.DataFrame) -> pd.DataFrame:
    """How often each payment method is used, and its revenue."""
    summary = df.groupby("Payment_Method").agg(
        Transactions=("Transaction_ID", "count"), Net_Revenue=("Net_Revenue", "sum"))
    summary["Usage_Percent"] = summary["Transactions"] / summary["Transactions"].sum() * 100
    return summary.sort_values("Transactions", ascending=False)


def top_transactions(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """The n highest net-revenue transactions, using ``nlargest``."""
    columns = ["Transaction_ID", "Date", "Product", "City", "Salesperson",
               "Quantity", "Net_Revenue", "Gross_Profit", "Gross_Profit_Margin"]
    return df.nlargest(n, "Net_Revenue")[columns]


def add_group_shares(df: pd.DataFrame) -> pd.DataFrame:
    """Use ``transform`` to add group totals to EVERY transaction row.

    ``agg`` gives ONE row per group. ``transform`` gives a value for EVERY
    original row (same index), so it can be stored as a new column. This
    is how we compute each transaction's share of its city's revenue.
    """
    result = df.copy()
    result["City_Total_Revenue"] = result.groupby("City")["Net_Revenue"].transform("sum")
    result["Share_of_City_Revenue_Percent"] = result["Net_Revenue"] / result["City_Total_Revenue"] * 100
    return result


def above_revenue_below_margin(df: pd.DataFrame) -> pd.DataFrame:
    """Transactions with above-average revenue but below-average margin.

    Uses ``query()``. The ``@`` symbol lets the query string use Python
    variables. "Average margin" is the OVERALL margin (total profit /
    total revenue).
    """
    avg_revenue = df["Net_Revenue"].mean()
    overall_margin = safe_margin(df["Gross_Profit"].sum(), df["Net_Revenue"].sum())
    return df.query("Net_Revenue > @avg_revenue and Gross_Profit_Margin < @overall_margin")


def sales_summary(df: pd.DataFrame) -> pd.DataFrame:
    """One table of headline metrics for sales_summary.csv."""
    summary = financial_summary(df)
    products = product_performance(df)
    cities = city_performance(df).dropna(subset=["Net_Revenue"])
    people = salesperson_performance(df)
    categories = category_performance(df)
    payments = payment_method_summary(df)
    extra = pd.DataFrame({
        "Metric": [
            "Highest-revenue product", "Most profitable product",
            "Highest-volume category (units)", "Highest-revenue city", "Most profitable city",
            "Highest-revenue salesperson", "Most profitable salesperson",
            "Most frequently used payment method",
        ],
        "Value": [
            products["Net_Revenue"].idxmax(), products["Gross_Profit"].idxmax(),
            categories["Units_Sold"].idxmax(), cities["Net_Revenue"].idxmax(),
            cities["Gross_Profit"].idxmax(), people["Net_Revenue"].idxmax(),
            people["Gross_Profit"].idxmax(), payments.index[0],
        ],
    })
    return pd.concat([summary, extra], ignore_index=True)


def reconcile_totals(grouped: pd.DataFrame, transactions: pd.DataFrame,
                     column: str = "Net_Revenue") -> bool:
    """Check that a grouped table adds up to the transaction-level total.

    If the totals differ, a grouping or join has lost or duplicated rows.
    """
    grouped_total = grouped[column].sum()  # NaN rows (e.g. Masvingo) are skipped
    transaction_total = transactions[column].sum()
    if not np.isclose(grouped_total, transaction_total, atol=MONEY_TOLERANCE):
        raise ValueError(f"Reconciliation failed for {column}: grouped={grouped_total}, "
                         f"transactions={transaction_total}")
    return True


# ===========================================================================
# STAGE 6: TIME-SERIES SALES ANALYSIS
# ===========================================================================
def add_date_parts(df: pd.DataFrame) -> pd.DataFrame:
    """Extract day, month and year using the ``.dt`` accessor."""
    result = df.copy()
    result["Day"] = result["Date"].dt.day
    result["Month"] = result["Date"].dt.month
    result["Year"] = result["Date"].dt.year
    result["Weekday"] = result["Date"].dt.day_name()
    return result


def daily_revenue(df: pd.DataFrame, raw_dates: pd.Series = None,
                  start="2026-01-01", end="2026-01-31") -> pd.DataFrame:
    """Build a daily table covering EVERY calendar day of the period.

    Days with no valid transactions get NaN revenue (unknown), NOT 0.
    The Day_Status column explains why a day is empty:
      * "Valid sales"           - at least one accepted transaction
      * "Only rejected records" - transactions existed but were rejected
      * "No records"            - nothing was recorded that day

    Two rolling averages are shown, because they mean different things:
      * Rolling_3_Transaction_Days: mean of the last 3 days that HAD sales
      * Rolling_3_Calendar_Days:    mean over the last 3 calendar days,
                                    using only the days with data
    """
    # Sort chronologically first. Strings would sort wrongly
    # ("12/01" before "6/01"), so we sort real datetimes.
    ordered = df.sort_values("Date")
    observed = ordered.groupby("Date").agg(
        Net_Revenue=("Net_Revenue", "sum"),
        Gross_Profit=("Gross_Profit", "sum"),
        Transaction_Count=("Transaction_ID", "count"),
    )
    observed["Rolling_3_Transaction_Days"] = observed["Net_Revenue"].rolling(window=3).mean()
    observed["Cumulative_Revenue"] = observed["Net_Revenue"].cumsum()

    calendar = pd.date_range(start, end, freq="D")
    daily = observed.reindex(calendar)
    daily.index.name = "Date"
    # A time-based window "3D" covers 3 calendar days. NaN days are
    # skipped (not counted as zero); min_periods=1 lets the window work
    # when some days have no data.
    daily["Rolling_3_Calendar_Days"] = daily["Net_Revenue"].rolling("3D", min_periods=1).mean()
    # Cumulative revenue stays flat on days with no data.
    daily["Cumulative_Revenue"] = daily["Cumulative_Revenue"].ffill()
    daily["Transaction_Count"] = daily["Transaction_Count"].fillna(0).astype(int)

    raw_days = set(pd.to_datetime(raw_dates)) if raw_dates is not None else set()
    daily["Day_Status"] = np.select(
        [daily["Net_Revenue"].notna(), daily.index.isin(list(raw_days))],
        ["Valid sales", "Only rejected records"],
        default="No records",
    )
    return daily


def compare_periods(df: pd.DataFrame, split_date="2026-01-15",
                    start="2026-01-05", end="2026-01-24") -> pd.DataFrame:
    """Compare two reporting periods of EQUAL calendar length.

    Data runs from 5 to 24 January (20 days), so we compare
    5-14 January against 15-24 January (10 days each). Results are shown
    as totals AND per calendar day, so different lengths could still be
    compared fairly.
    """
    start, split, end = pd.Timestamp(start), pd.Timestamp(split_date), pd.Timestamp(end)
    periods = {
        f"{start.date()} to {(split - pd.Timedelta(days=1)).date()}": (start, split - pd.Timedelta(days=1)),
        f"{split.date()} to {end.date()}": (split, end),
    }
    rows = []
    for label, (p_start, p_end) in periods.items():
        part = df.loc[df["Date"].between(p_start, p_end)]
        days = (p_end - p_start).days + 1
        rows.append({
            "Period": label, "Calendar_Days": days,
            "Days_With_Valid_Sales": part["Date"].nunique(),
            "Transactions": len(part), "Net_Revenue": part["Net_Revenue"].sum(),
            "Gross_Profit": part["Gross_Profit"].sum(),
            "Revenue_per_Calendar_Day": part["Net_Revenue"].sum() / days,
        })
    result = pd.DataFrame(rows)
    first, second = result["Net_Revenue"].iloc[0], result["Net_Revenue"].iloc[1]
    result["Change_vs_Previous_Percent"] = [np.nan, (second - first) / first * 100 if first else np.nan]
    return result


# ===========================================================================
# STAGE 7: PRODUCT AND SALES SEGMENTATION
# ===========================================================================
def classify_transaction_value(df: pd.DataFrame):
    """Label each transaction High, Medium or Low by net revenue.

    THRESHOLD JUSTIFICATION: we use the 33rd and 67th percentiles
    (tertiles) of net revenue. This gives about one third of transactions
    in each group and follows the data rather than a guessed number.
    The thresholds are returned so they can be documented.

    The conditions do not overlap (<= q1, q1 < x <= q2, > q2), and
    ``np.select`` has a default, so every transaction gets a label.
    """
    q1, q2 = df["Net_Revenue"].quantile([1 / 3, 2 / 3])
    result = df.copy()
    result["Value_Segment"] = np.select(
        [result["Net_Revenue"] <= q1, result["Net_Revenue"] <= q2],
        ["Low", "Medium"],
        default="High",
    )
    return result, {"low_upper_bound": q1, "medium_upper_bound": q2}


def segment_products(df: pd.DataFrame) -> pd.DataFrame:
    """Classify products using BOTH revenue share and margin.

    * Revenue benchmark: an equal share (100 % / number of products).
    * Margin benchmark: the overall company margin.

    High performer   = above both benchmarks
    Revenue driver   = high revenue, low margin
    Margin niche     = low revenue, high margin (low revenue != unprofitable)
    Underperformer   = below both benchmarks
    """
    products = product_performance(df)
    equal_share = 100 / len(products)
    overall_margin = safe_margin(df["Gross_Profit"].sum(), df["Net_Revenue"].sum())
    high_rev = products["Revenue_Share_Percent"] >= equal_share
    high_margin = products["Gross_Profit_Margin"] >= overall_margin
    products["Segment"] = np.select(
        [high_rev & high_margin, high_rev & ~high_margin, ~high_rev & high_margin],
        ["High performer", "Revenue driver (low margin)", "Margin niche (low revenue)"],
        default="Underperformer",
    )
    products["Low_Margin"] = ~high_margin
    return products


def segment_categories(df: pd.DataFrame) -> pd.DataFrame:
    """Classify categories with the same two-benchmark logic as products."""
    categories = category_performance(df)
    equal_share = 100 / len(categories)
    overall_margin = safe_margin(df["Gross_Profit"].sum(), df["Net_Revenue"].sum())
    high_rev = categories["Revenue_Share_Percent"] >= equal_share
    high_margin = categories["Gross_Profit_Margin"] >= overall_margin
    categories["Category_Class"] = np.select(
        [high_rev & high_margin, high_rev & ~high_margin, ~high_rev & high_margin],
        ["Core - high revenue & margin", "Core - revenue driver, low margin", "Niche - high margin"],
        default="Niche - low revenue & margin",
    )
    return categories


def high_discount_transactions(df: pd.DataFrame):
    """Find unusually high discounts: above the 75th percentile.

    The 75th percentile (upper quartile) is a common, transparent cut-off
    for "unusually high". Returns the rows and the threshold.
    """
    threshold = df["Discount_Percent"].quantile(0.75)
    return df.loc[df["Discount_Percent"] > threshold], threshold


# ===========================================================================
# STAGE 8: MULTI-DATAFRAME OPERATIONS
# ===========================================================================
# Product reference data (a second dictionary). Tablet has no sales, so
# it shows how unmatched records appear. "  mouse" is deliberately messy
# to show that reference names are standardised too.
product_reference_data = {
    "Product_Code": ["P001", "P002", "P003", "P004", "P005", "P006", "P007"],
    "Product_Name": ["Laptop", "Smartphone", "Keyboard", "Monitor", "Printer", "  mouse", "Tablet"],
    "Product_Category": ["Computers", "Mobile", "Accessories", "Computers",
                         "Office Equipment", "Accessories", "Mobile"],
    "Reorder_Threshold": [5, 10, 20, 5, 3, 25, 8],
}

PRODUCT_CODE_PATTERN = re.compile(r"^P\d{3}$")


def build_reference_dataframe(reference_dict=None) -> pd.DataFrame:
    """Build and validate the product reference DataFrame.

    Checks: codes match the pattern P### and are unique; product names
    (after standardising) are unique, so each sale matches AT MOST one
    reference row and the merge cannot duplicate sales.
    """
    ref = pd.DataFrame(reference_dict or product_reference_data)
    ref["Product_Name"] = ref["Product_Name"].astype(str).str.strip().str.title()

    bad_codes = ref.loc[~ref["Product_Code"].astype(str).str.match(PRODUCT_CODE_PATTERN), "Product_Code"]
    if not bad_codes.empty:
        raise ValueError(f"Invalid product codes: {bad_codes.tolist()}")
    if ref["Product_Code"].duplicated().any():
        raise ValueError("Product codes are not unique.")
    if ref["Product_Name"].duplicated().any():
        raise ValueError("Product names are not unique in the reference data.")
    return ref


def merge_sales_with_reference(sales: pd.DataFrame, reference: pd.DataFrame, how: str = "left"):
    """Merge sales (many rows per product) with reference data (one row
    per product).

    ``validate="many_to_one"`` makes pandas RAISE an error if the reference
    has duplicate keys, which stops accidental revenue duplication.
    ``indicator=True`` adds a ``_merge`` column showing where each row
    matched.
    """
    return sales.merge(reference, how=how, left_on="Product", right_on="Product_Name",
                       validate="many_to_one", indicator=True)


def merge_report(sales: pd.DataFrame, reference: pd.DataFrame) -> dict:
    """Run inner, left and outer joins and check they are correct.

    * Row counts and revenue must be the same before and after a left join.
    * Unmatched sales (in sales, not in reference) are listed.
    * Unused reference products (in reference, not in sales) are listed.
    * Sales categories are compared with reference categories.
    """
    left = merge_sales_with_reference(sales, reference, "left")
    inner = merge_sales_with_reference(sales, reference, "inner")
    outer = merge_sales_with_reference(sales, reference, "outer")

    unmatched_sales = left.loc[left["_merge"] == "left_only", ["Transaction_ID", "Product"]]
    unused_reference = outer.loc[outer["_merge"] == "right_only", ["Product_Code", "Product_Name"]]
    category_mismatch = left.loc[(left["_merge"] == "both") &
                                 (left["Category"] != left["Product_Category"]),
                                 ["Transaction_ID", "Product", "Category", "Product_Category"]]

    checks = pd.DataFrame({
        "Check": ["Rows before merge", "Rows after left join", "Rows after inner join",
                  "Revenue before merge", "Revenue after left join",
                  "Duplicate Transaction_IDs after merge", "Unmatched sales rows",
                  "Reference products with no sales", "Category mismatches"],
        "Value": [len(sales), len(left), len(inner), sales["Net_Revenue"].sum(),
                  left["Net_Revenue"].sum(), int(left["Transaction_ID"].duplicated().sum()),
                  len(unmatched_sales), len(unused_reference), len(category_mismatch)],
    })
    if len(left) != len(sales) or left["Transaction_ID"].duplicated().any():
        raise ValueError("Merge changed the number of transactions.")
    reconcile_totals(left, sales)
    return {"left": left, "inner": inner, "checks": checks, "unmatched_sales": unmatched_sales,
            "unused_reference": unused_reference, "category_mismatch": category_mismatch}


def city_category_pivot(df: pd.DataFrame) -> pd.DataFrame:
    """Net revenue pivot: cities as rows, categories as columns.

    ``pivot_table`` (not ``pivot``) is used because it AGGREGATES
    duplicates with ``aggfunc``. ``pivot`` fails if a city/category pair
    appears more than once. ``margins=True`` adds row and column totals.
    An empty cell (0) means no sales of that category in that city IN
    THIS SAMPLE.
    """
    return pd.pivot_table(df, values="Net_Revenue", index="City", columns="Category",
                          aggfunc="sum", fill_value=0, margins=True, margins_name="Total")


# ===========================================================================
# STAGE 9: ADVANCED MANIPULATION AND BUSINESS INTELLIGENCE
# ===========================================================================
def city_category_aggregation(df: pd.DataFrame) -> pd.DataFrame:
    """Multi-level aggregation: group by City AND Category (MultiIndex)."""
    result = df.groupby(["City", "Category"]).agg(
        Transactions=("Transaction_ID", "count"),
        Net_Revenue=("Net_Revenue", "sum"),
        Gross_Profit=("Gross_Profit", "sum"),
    )
    result["Gross_Profit_Margin"] = safe_margin(result["Gross_Profit"], result["Net_Revenue"])
    return result


def rank_salespeople_within_city(df: pd.DataFrame) -> pd.DataFrame:
    """Rank salespeople inside each city by their TOTAL revenue.

    We aggregate first (one row per city + salesperson) and THEN rank, so
    we rank people, not individual transactions.
    """
    totals = df.groupby(["City", "Salesperson"], as_index=False).agg(
        Net_Revenue=("Net_Revenue", "sum"), Gross_Profit=("Gross_Profit", "sum"),
        Transactions=("Transaction_ID", "count"))
    totals["Rank_in_City"] = (totals.groupby("City")["Net_Revenue"]
                              .rank(ascending=False, method="min").astype(int))
    return totals.sort_values(["City", "Rank_in_City"]).reset_index(drop=True)


def classify_salesperson_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Performance classes compared with the salesperson averages.

    Strong   : revenue AND profit at/above average
    Mixed    : one of the two at/above average
    Develop  : both below average
    """
    people = salesperson_performance(df)
    rev_ok = people["Net_Revenue"] >= people["Net_Revenue"].mean()
    prof_ok = people["Gross_Profit"] >= people["Gross_Profit"].mean()
    people["Performance_Class"] = np.select([rev_ok & prof_ok, rev_ok | prof_ok],
                                            ["Strong", "Mixed"], default="Develop")
    return people


def cumulative_revenue_by_city(df: pd.DataFrame) -> pd.DataFrame:
    """Running revenue total for each city separately.

    Sort by City then Date FIRST, because cumsum adds rows in the order
    they appear.
    """
    ordered = df.sort_values(["City", "Date"]).copy()
    ordered["City_Cumulative_Revenue"] = ordered.groupby("City")["Net_Revenue"].cumsum()
    return ordered[["City", "Date", "Transaction_ID", "Net_Revenue", "City_Cumulative_Revenue"]]


def product_share_within_category(df: pd.DataFrame) -> pd.DataFrame:
    """Each product's share of its category's revenue (uses transform)."""
    products = df.groupby(["Category", "Product"], as_index=False)["Net_Revenue"].sum()
    products["Category_Revenue"] = products.groupby("Category")["Net_Revenue"].transform("sum")
    products["Share_of_Category_Percent"] = products["Net_Revenue"] / products["Category_Revenue"] * 100
    return products.sort_values(["Category", "Net_Revenue"], ascending=[True, False])


def top_profitable_categories(df: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    """The n categories with the highest total gross profit."""
    return category_performance(df).nlargest(n, "Gross_Profit")[
        ["Net_Revenue", "Gross_Profit", "Gross_Profit_Margin"]]


def compare_original_and_processed(raw_df: pd.DataFrame, cleaned_df: pd.DataFrame,
                                   rejected_df: pd.DataFrame) -> pd.DataFrame:
    """Side-by-side comparison of the raw and processed datasets.

    The "naive" revenue is what you would get by multiplying the raw
    numbers without cleaning (missing price treated as unknown and
    skipped). It shows the financial effect of rejecting records.
    """
    raw_gross = (raw_df["Quantity"] * raw_df["Unit_Price"]).sum()  # NaN price is skipped
    return pd.DataFrame({
        "Measure": ["Records", "Distinct product spellings", "Distinct date formats/strings",
                    "Missing Unit_Price values", "Non-positive quantities",
                    "Gross revenue Q x P (USD)"],
        "Original": [len(raw_df), raw_df["Product"].nunique(), raw_df["Date"].nunique(),
                     int(raw_df["Unit_Price"].isna().sum()), int((raw_df["Quantity"] <= 0).sum()),
                     raw_gross],
        "Processed": [len(cleaned_df), cleaned_df["Product"].nunique(), cleaned_df["Date"].nunique(),
                      int(cleaned_df["Unit_Price"].isna().sum()), int((cleaned_df["Quantity"] <= 0).sum()),
                      cleaned_df["Gross_Revenue"].sum() if "Gross_Revenue" in cleaned_df else np.nan],
        "Rejected": [len(rejected_df), "", "", int(rejected_df["Unit_Price"].isna().sum()),
                     int((rejected_df["Quantity"] <= 0).sum()),
                     (rejected_df["Quantity"] * rejected_df["Unit_Price"]).sum()],
    })


def rejected_financial_impact(rejected_df: pd.DataFrame) -> pd.DataFrame:
    """Show the revenue each rejected record WOULD represent, if known.

    This is for reporting only. These values are NOT in any total.
    """
    impact = rejected_df[["Transaction_ID", "Product", "Quantity", "Unit_Price",
                          "Unit_Cost", "Discount_Percent", "Rejection_Reason"]].copy()
    impact["Potential_Net_Revenue"] = (impact["Quantity"] * impact["Unit_Price"]
                                       * (1 - impact["Discount_Percent"] / 100))
    return impact
