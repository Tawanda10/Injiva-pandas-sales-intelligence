"""
pipeline.py
===========
STAGE 11: reusable end-to-end data processing pipeline.

Run from the project root folder:

    python -m src.pipeline

What the pipeline does, in order:
    1. Build the DataFrame from a COPY of the source dictionary
    2. Validate the schema (structure)
    3. Assess data quality (business rules) -> data_quality_report.csv
    4. Clean and split records             -> cleaned_sales.csv, rejected_records.csv
    5. Add financial columns and verify them
    6. Aggregate and analyse               -> summary CSV files
    7. Validate everything, THEN export

Design choices:
* Each step is its own function (separation of concerns).
* No global variables are changed. Data moves between steps as function
  arguments and return values.
* The output folder is found RELATIVE to this file, so the project works
  on any computer, with no hard-coded "C:/Users/..." paths.
* Running it twice gives identical results (reproducible).
"""

from pathlib import Path

import pandas as pd

from src import analytics, cleaning, validation
from src.source_data import get_sales_data

# Project root = the folder that contains "src". Path(__file__) is this file.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data"


# ---------------------------------------------------------------------------
# Step functions (each has ONE clear responsibility)
# ---------------------------------------------------------------------------
def construct_dataframe(source_dict=None) -> pd.DataFrame:
    """Step 1: build the raw DataFrame from a copy of the source data."""
    return validation.build_sales_dataframe(source_dict or get_sales_data())


def validate_structure(raw_df: pd.DataFrame) -> dict:
    """Step 2: schema validation. Raises SchemaValidationError if wrong."""
    return validation.validate_schema(raw_df)


def assess_quality(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Step 3: rule-based data quality report."""
    return validation.run_data_quality_checks(raw_df)


def clean(raw_df: pd.DataFrame):
    """Step 4: cleaning. Returns (cleaned, rejected, summary)."""
    return cleaning.clean_sales_data(raw_df)


def transform_financials(cleaned_df: pd.DataFrame) -> pd.DataFrame:
    """Step 5: add financial columns and verify them independently."""
    financial_df = analytics.add_financial_columns(cleaned_df)
    analytics.verify_financial_calculations(financial_df)
    return financial_df


def aggregate_sales(financial_df: pd.DataFrame) -> dict:
    """Step 6a: grouped performance tables, each reconciled to the total."""
    tables = {
        "sales_summary": analytics.sales_summary(financial_df),
        "city_performance": analytics.city_performance(financial_df),
        "product_performance": analytics.product_performance(financial_df),
        "salesperson_performance": analytics.classify_salesperson_performance(financial_df),
    }
    for name in ["city_performance", "product_performance", "salesperson_performance"]:
        analytics.reconcile_totals(tables[name], financial_df)
    return tables


def analyse_performance(financial_df: pd.DataFrame, raw_df: pd.DataFrame) -> dict:
    """Step 6b: extra analyses (used by the notebook and the report)."""
    segmented, thresholds = analytics.classify_transaction_value(financial_df)
    return {
        "segmented_transactions": segmented,
        "value_thresholds": thresholds,
        "daily_revenue": analytics.daily_revenue(
            financial_df, raw_dates=raw_df["Date"].apply(validation.parse_date_value)),
        "period_comparison": analytics.compare_periods(financial_df),
        "merge": analytics.merge_report(financial_df, analytics.build_reference_dataframe()),
        "city_category_pivot": analytics.city_category_pivot(financial_df),
    }


def export_results(outputs: dict, output_dir: Path) -> list:
    """Step 7: write each DataFrame to CSV and return the file paths.

    The index is written only when it holds meaningful labels
    (City, Product, Salesperson); a plain 0, 1, 2... index is skipped.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, frame in outputs.items():
        path = output_dir / f"{name}.csv"
        keep_index = frame.index.name is not None
        frame.to_csv(path, index=keep_index, float_format="%.2f", date_format="%Y-%m-%d")
        written.append(path)
    return written


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def run_pipeline(output_dir=DEFAULT_OUTPUT_DIR, source_dict=None, export=True) -> dict:
    """Run every step from start to finish and return all results.

    ``source_dict`` lets tests pass a small custom dataset.
    ``export=False`` runs everything without writing files.
    """
    raw_df = construct_dataframe(source_dict)
    schema_report = validate_structure(raw_df)
    quality_report = assess_quality(raw_df)
    cleaned_df, rejected_df, cleaning_summary = clean(raw_df)
    financial_df = transform_financials(cleaned_df)
    tables = aggregate_sales(financial_df)

    # Final check before export: cleaned data must still pass all rules.
    validation.validate_cleaned_data(financial_df)

    results = {
        "raw": raw_df, "schema_report": schema_report, "quality_report": quality_report,
        "cleaned": financial_df, "rejected": rejected_df, "cleaning_summary": cleaning_summary,
        **tables,
    }
    if export:
        results["files"] = export_results({
            "cleaned_sales": financial_df,
            "rejected_records": rejected_df,
            "data_quality_report": quality_report,
            **tables,
        }, output_dir)
    return results


def main():
    """Command-line entry point: run the pipeline and print a summary."""
    results = run_pipeline()
    print("Pipeline completed successfully.")
    print(f"  Source records : {len(results['raw'])}")
    print(f"  Accepted       : {len(results['cleaned'])}")
    print(f"  Rejected       : {len(results['rejected'])}")
    print("  Files written  :")
    for path in results["files"]:
        print(f"    - {path.relative_to(PROJECT_ROOT)}")
    print()
    print(results["sales_summary"].to_string(index=False))


if __name__ == "__main__":
    main()
