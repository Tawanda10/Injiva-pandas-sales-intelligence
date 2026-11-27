"""
test_sales_pipeline.py
======================
STAGE 10: automated tests (run with:  python -m pytest -v).

How these tests are written:
* Each test checks ONE business rule.
* Expected values are worked out BY HAND and typed in as numbers. We do
  NOT reuse the production formula inside the test, because then a wrong
  formula would "agree with itself" and the test would pass anyway.
* Both success AND failure cases are tested, including deliberately
  invalid records.
* Tests build their own small datasets, so they never change the
  source data (the source data itself is checked at the end).
"""

import copy

import numpy as np
import pandas as pd
import pytest

from src import analytics, cleaning, validation
from src.pipeline import run_pipeline
from src.source_data import get_sales_data, sales_data


# ---------------------------------------------------------------------------
# Fixtures: reusable small test datasets
# ---------------------------------------------------------------------------
# A pytest "fixture" is a function that prepares data for a test. A test
# receives it by naming it as a parameter.

@pytest.fixture
def small_valid_dict():
    """Three valid transactions with easy numbers to check by hand."""
    return {
        "Transaction_ID": ["T1", "T2", "T3"],
        "Date": ["2026-01-05", "06/01/2026", "07-01-2026"],
        "Product": ["Laptop", "mouse", "PRINTER"],
        "Category": ["Computers", "Accessories", "Office Equipment"],
        "Quantity": [2, 10, 1],
        "Unit_Price": [100.0, 10.0, 50.0],
        "Unit_Cost": [80.0, 4.0, 60.0],      # T3 is sold below cost -> loss
        "Salesperson": ["A", "B", "A"],
        "City": ["Harare", "Gweru", "Harare"],
        "Payment_Method": ["Cash", "EcoCash", "Cash"],
        "Discount_Percent": [10, 0, 0],
    }


@pytest.fixture
def small_valid_df(small_valid_dict):
    return validation.build_sales_dataframe(small_valid_dict)


# ---------------------------------------------------------------------------
# 1. Mandatory columns
# ---------------------------------------------------------------------------
def test_schema_passes_for_source_data():
    df = validation.build_sales_dataframe(get_sales_data())
    assert validation.validate_schema(df)["status"] == "PASSED"


def test_missing_mandatory_column_raises_clear_error(small_valid_df):
    broken = small_valid_df.drop(columns=["Unit_Price"])
    with pytest.raises(validation.SchemaValidationError, match="Unit_Price"):
        validation.validate_schema(broken)


def test_unequal_list_lengths_are_detected(small_valid_dict):
    small_valid_dict["Quantity"] = [1, 2]  # one value short
    with pytest.raises(validation.SchemaValidationError, match="inconsistent lengths"):
        validation.check_list_lengths(small_valid_dict)


# ---------------------------------------------------------------------------
# 2. Unique transaction identifiers
# ---------------------------------------------------------------------------
def test_duplicate_transaction_id_is_reported_and_rejected(small_valid_dict):
    small_valid_dict["Transaction_ID"] = ["T1", "T1", "T3"]   # deliberately invalid
    df = validation.build_sales_dataframe(small_valid_dict)
    report = validation.run_data_quality_checks(df)
    assert (report["Rule_ID"] == "R02").sum() == 2
    reasons = cleaning.identify_rejection_reasons(cleaning.correct_numeric_types(df))
    assert reasons.str.contains("Duplicate Transaction_ID").sum() == 2


# ---------------------------------------------------------------------------
# 3 & 4. Valid quantities and unit prices (DELIBERATELY INVALID RECORDS)
# ---------------------------------------------------------------------------
def test_invalid_records_are_rejected_not_deleted(small_valid_dict):
    # Add three deliberately invalid records.
    bad = {
        "Transaction_ID": ["BAD1", "BAD2", "BAD3"], "Date": ["2026-01-10"] * 3,
        "Product": ["Laptop"] * 3, "Category": ["Computers"] * 3,
        "Quantity": [-1, 0, 2], "Unit_Price": [100.0, 100.0, None],
        "Unit_Cost": [80.0] * 3, "Salesperson": ["A"] * 3, "City": ["Harare"] * 3,
        "Payment_Method": ["Cash"] * 3, "Discount_Percent": [0] * 3,
    }
    combined = {k: small_valid_dict[k] + bad[k] for k in small_valid_dict}
    cleaned, rejected, _ = cleaning.clean_sales_data(pd.DataFrame(combined))

    assert sorted(rejected["Transaction_ID"]) == ["BAD1", "BAD2", "BAD3"]
    assert sorted(cleaned["Transaction_ID"]) == ["T1", "T2", "T3"]
    assert len(cleaned) + len(rejected) == 6          # nothing silently lost
    # The missing price must NOT have been filled in with 0 or an average.
    assert rejected.loc[rejected["Transaction_ID"] == "BAD3", "Unit_Price"].isna().all()


def test_quality_report_flags_source_problems():
    report = validation.run_data_quality_checks(pd.DataFrame(get_sales_data()))
    flagged = set(report.loc[report["Transaction_ID"] != "ALL", "Transaction_ID"])
    assert {"TX009", "TX012", "TX015"} <= flagged
    # A rule that finds nothing still reports that it passed.
    assert (report.loc[report["Rule_ID"] == "R02", "Resolution_Status"] == "Passed").all()


# ---------------------------------------------------------------------------
# 5. Correct discounts (including boundaries)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("discount, should_reject", [
    (0, False), (100, False),      # boundaries are allowed
    (-1, True), (101, True),       # just outside the boundaries
])
def test_discount_boundaries(small_valid_dict, discount, should_reject):
    small_valid_dict["Discount_Percent"] = [discount, 0, 0]
    df = cleaning.correct_numeric_types(pd.DataFrame(small_valid_dict))
    df["Product"] = cleaning.standardise_product_names(df["Product"])
    df["Date"] = cleaning.convert_dates(df["Date"])
    reasons = cleaning.identify_rejection_reasons(df)
    assert (reasons.iloc[0] != "") == should_reject


def test_discount_amount_uses_percentage_divided_by_100(small_valid_df):
    cleaned, _, _ = cleaning.clean_sales_data(small_valid_df)
    fin = analytics.add_financial_columns(cleaned).set_index("Transaction_ID")
    # T1: gross 2 x 100 = 200; 10 % discount = 20 (not 2000!)
    assert fin.loc["T1", "Discount_Amount"] == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# 6 & 7. Correct revenue and gross profit (hand-calculated values)
# ---------------------------------------------------------------------------
def test_revenue_and_profit_calculations(small_valid_df):
    cleaned, _, _ = cleaning.clean_sales_data(small_valid_df)
    fin = analytics.add_financial_columns(cleaned).set_index("Transaction_ID")
    # T1: net = 200 - 20 = 180; cost = 160; profit = 20; margin = 11.11 %
    assert fin.loc["T1", "Net_Revenue"] == pytest.approx(180.0)
    assert fin.loc["T1", "Gross_Profit"] == pytest.approx(20.0)
    assert fin.loc["T1", "Gross_Profit_Margin"] == pytest.approx(11.1111, abs=1e-3)
    # T3: net = 50, cost = 60 -> loss of 10
    assert fin.loc["T3", "Gross_Profit"] == pytest.approx(-10.0)
    assert list(analytics.loss_making_transactions(fin.reset_index())["Transaction_ID"]) == ["T3"]


def test_overall_margin_is_total_profit_over_total_revenue(small_valid_df):
    cleaned, _, _ = cleaning.clean_sales_data(small_valid_df)
    fin = analytics.add_financial_columns(cleaned)
    summary = analytics.financial_summary(fin).set_index("Metric")["Value"]
    # Totals: revenue 180 + 100 + 50 = 330; profit 20 + 60 - 10 = 70
    # Correct: 70 / 330 = 21.21 %. The WRONG way (mean of 11.11, 60, -20) gives 17.04 %.
    assert summary["Overall gross profit margin (%)"] == pytest.approx(21.21, abs=0.01)


def test_margin_handles_division_by_zero():
    margins = analytics.safe_margin([10, 0], [0, 0])
    assert np.isnan(margins).all()


def test_full_dataset_totals_match_hand_calculation():
    results = run_pipeline(export=False)
    fin = results["cleaned"]
    assert len(fin) == 17
    assert fin["Net_Revenue"].sum() == pytest.approx(13340.50, abs=0.01)
    assert fin["Gross_Profit"].sum() == pytest.approx(3255.50, abs=0.01)


# ---------------------------------------------------------------------------
# 8. Valid dates
# ---------------------------------------------------------------------------
def test_dates_parsed_day_first_and_invalid_dates_rejected():
    assert validation.parse_date_value("06/01/2026") == pd.Timestamp("2026-01-06")
    assert validation.parse_date_value("09-01-2026") == pd.Timestamp("2026-01-09")
    assert pd.isna(validation.parse_date_value("2026/13/45"))   # deliberately invalid


# ---------------------------------------------------------------------------
# 9. Successful DataFrame merges
# ---------------------------------------------------------------------------
def test_merge_keeps_row_count_and_revenue():
    fin = run_pipeline(export=False)["cleaned"]
    report = analytics.merge_report(fin, analytics.build_reference_dataframe())
    assert len(report["left"]) == len(fin)
    assert report["unmatched_sales"].empty
    assert list(report["unused_reference"]["Product_Name"]) == ["Tablet"]


def test_merge_rejects_duplicate_reference_keys():
    ref = copy.deepcopy(analytics.product_reference_data)
    ref["Product_Name"][1] = "Laptop"             # deliberately duplicated name
    with pytest.raises(ValueError, match="not unique"):
        analytics.build_reference_dataframe(ref)


# ---------------------------------------------------------------------------
# 10. Financial reconciliation
# ---------------------------------------------------------------------------
def test_grouped_totals_reconcile_with_transactions():
    results = run_pipeline(export=False)
    fin = results["cleaned"]
    for table in ["city_performance", "product_performance", "salesperson_performance"]:
        assert analytics.reconcile_totals(results[table], fin)


def test_reconciliation_detects_a_mismatch():
    fin = run_pipeline(export=False)["cleaned"]
    tampered = analytics.product_performance(fin)
    tampered.loc["Laptop", "Net_Revenue"] += 100       # deliberate error
    with pytest.raises(ValueError, match="Reconciliation failed"):
        analytics.reconcile_totals(tampered, fin)


# ---------------------------------------------------------------------------
# Data integrity: the original dictionary must never change
# ---------------------------------------------------------------------------
def test_source_data_is_not_modified():
    snapshot = copy.deepcopy(sales_data)
    run_pipeline(export=False)
    assert sales_data == snapshot
