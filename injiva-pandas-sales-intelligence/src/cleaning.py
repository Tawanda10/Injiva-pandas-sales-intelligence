"""
cleaning.py
===========
STAGE 3: data cleaning and standardisation.

Main ideas used in this module:
* Every function takes a DataFrame or Series and returns a NEW one. The
  input is never changed in place, so the original data stays intact.
* Nothing is invented. A missing price is never replaced with 0 or an
  average. Records we cannot trust go to a "rejected" table with a reason.
* Every change is recorded. We keep the original values in
  ``Original_*`` columns and describe what changed in ``Cleaning_Notes``.
* The same input always gives the same output (deterministic), because
  dates use explicit formats and rules are fixed in code.

DOCUMENTED CLEANING ASSUMPTIONS
-------------------------------
A1  Product names are standardised to Title Case ("LAPTOP" -> "Laptop").
A2  Dates are parsed with explicit formats: YYYY-MM-DD, DD/MM/YYYY,
    DD-MM-YYYY. Slashed and dashed dates are read DAY FIRST because all
    transactions are from January 2026.
A3  Missing Unit_Price: the record is REJECTED for manual review. We do
    not impute: other Printer prices (220 and 230) differ, so any guess
    would be invented revenue.
A4  Negative Quantity: possibly a return, but there is no link to an
    original sale, so it is REJECTED pending confirmation.
A5  Zero Quantity: no goods moved. REJECTED as a non-transaction.
A6  Discounts outside 0-100 % are REJECTED. Discounts above 30 % are
    accepted but flagged for manual review (policy check).
A7  Rejected records are kept in rejected_records.csv with their reason,
    so no record disappears silently.
"""

import pandas as pd

from src.validation import (
    MAX_DISCOUNT, MAX_POLICY_DISCOUNT, MIN_DISCOUNT, PRODUCT_CATEGORY_MAP,
    parse_date_value, validate_cleaned_data,
)


# ===========================================================================
# SECTION A: SMALL, SINGLE-PURPOSE CLEANING FUNCTIONS
# ===========================================================================
def standardise_product_names(products: pd.Series) -> pd.Series:
    """Remove extra spaces and convert names to Title Case.

    Example: ' LAPTOP ' -> 'Laptop', 'keyboard' -> 'Keyboard'.
    The ``.str`` methods work on the whole column at once (vectorised).
    """
    return products.astype(str).str.strip().str.title()


def convert_dates(dates: pd.Series) -> pd.Series:
    """Convert mixed-format date strings into proper datetime values.

    Uses ``parse_date_value`` from validation.py, which tries each
    explicit format in turn. Unparseable dates become NaT and are later
    rejected rather than guessed.
    """
    return pd.to_datetime(dates.apply(parse_date_value))


def correct_numeric_types(df: pd.DataFrame) -> pd.DataFrame:
    """Make sure numeric columns really are numeric.

    ``errors='coerce'`` turns anything that is not a number into NaN so it
    can be caught by the rejection rules, instead of crashing the program.
    Money columns use float, which is standard for pandas currency work.
    """
    result = df.copy()
    result["Quantity"] = pd.to_numeric(result["Quantity"], errors="coerce")
    for column in ["Unit_Price", "Unit_Cost", "Discount_Percent"]:
        result[column] = pd.to_numeric(result[column], errors="coerce").astype("float64")
    return result


def identify_rejection_reasons(df: pd.DataFrame) -> pd.Series:
    """Return a text Series giving the reason(s) each row must be rejected.

    An empty string means the row is acceptable. A row can have several
    reasons; they are joined with '; '.

    Each rule is a Boolean mask. ``Series.where`` puts the reason text on
    rows where the mask is True and an empty string elsewhere.
    """
    rules = {
        "Missing Unit_Price (not imputed - needs actual price)": df["Unit_Price"].isna(),
        "Non-positive Unit_Price": df["Unit_Price"].notna() & (df["Unit_Price"] <= 0),
        "Invalid Unit_Cost": df["Unit_Cost"].isna() | (df["Unit_Cost"] <= 0),
        "Negative Quantity (possible return - no original sale reference)": df["Quantity"] < 0,
        "Zero Quantity (no goods sold)": df["Quantity"] == 0,
        "Missing/invalid Quantity": df["Quantity"].isna(),
        "Discount outside 0-100%": ~df["Discount_Percent"].between(MIN_DISCOUNT, MAX_DISCOUNT),
        "Unparseable Date": df["Date"].isna(),
        "Unknown Product": ~df["Product"].isin(PRODUCT_CATEGORY_MAP.keys()),
        "Duplicate Transaction_ID": df["Transaction_ID"].duplicated(keep=False),
    }
    reasons = pd.Series("", index=df.index)
    for reason_text, mask in rules.items():
        addition = pd.Series(reason_text, index=df.index).where(mask, "")
        # Add "; " between reasons only when both sides have text.
        separator = pd.Series("; ", index=df.index).where((reasons != "") & (addition != ""), "")
        reasons = reasons + separator + addition
    return reasons


def flag_manual_review(df: pd.DataFrame) -> pd.Series:
    """Flag records that are accepted but should be checked by a person.

    Currently: discounts above the policy limit (30 %).
    """
    return df["Discount_Percent"] > MAX_POLICY_DISCOUNT


def separate_accepted_rejected(df: pd.DataFrame):
    """Split rows into accepted and rejected DataFrames using the
    ``Rejection_Reason`` column. Returns (accepted, rejected).
    """
    is_rejected = df["Rejection_Reason"] != ""
    accepted = df.loc[~is_rejected].drop(columns=["Rejection_Reason"]).reset_index(drop=True)
    rejected = df.loc[is_rejected].reset_index(drop=True)
    return accepted, rejected


def verify_no_new_duplicates(original: pd.DataFrame, cleaned: pd.DataFrame) -> None:
    """Confirm that cleaning did not create duplicate transactions.

    Cleaning should only REMOVE rows, so cleaned IDs must be unique and
    must all exist in the original data.
    """
    if cleaned["Transaction_ID"].duplicated().any():
        raise ValueError("Cleaning introduced duplicate Transaction_IDs.")
    unknown_ids = set(cleaned["Transaction_ID"]) - set(original["Transaction_ID"])
    if unknown_ids:
        raise ValueError(f"Cleaning introduced unknown Transaction_IDs: {unknown_ids}")


# ===========================================================================
# SECTION B: THE MAIN CLEANING FUNCTION
# ===========================================================================
def clean_sales_data(raw_df: pd.DataFrame):
    """Run the full cleaning process.

    Steps:
      1. Work on a COPY of the raw data.
      2. Keep original Product and Date values (audit trail).
      3. Standardise products, convert dates, fix numeric types.
      4. Record what changed in each row (Cleaning_Notes).
      5. Find rejection reasons and manual-review flags.
      6. Split into accepted and rejected records.
      7. Verify no duplicates were created and validate the result.

    Returns:
      cleaned_df  : accepted records, ready for financial calculations
      rejected_df : rejected records with a Rejection_Reason column
      summary_df  : a small table summarising what cleaning did
    """
    # Step 1: independent working copy, so the raw DataFrame is untouched.
    working = raw_df.copy()

    # Step 2: preserve original values for auditing.
    working["Original_Product"] = raw_df["Product"].astype(str)
    working["Original_Date"] = raw_df["Date"].astype(str)

    # Step 3: transformations. Each uses a full-column assignment, never
    # chained indexing like df[...][...] = value.
    working["Product"] = standardise_product_names(working["Product"])
    working["Date"] = convert_dates(working["Date"])
    working = correct_numeric_types(working)

    # Step 4: describe changes made to each row.
    product_changed = working["Product"] != working["Original_Product"]
    date_reformatted = working["Date"].dt.strftime("%Y-%m-%d") != working["Original_Date"]
    notes = pd.Series("", index=working.index)
    notes = notes.where(~product_changed,
                        "Product standardised from '" + working["Original_Product"] + "'")
    date_note = "Date converted from '" + working["Original_Date"] + "' (day-first)"
    notes = notes.where(~date_reformatted,
                        notes.where(notes == "", notes + "; ") + date_note)
    working["Cleaning_Notes"] = notes

    # Step 5: rejection reasons and review flags.
    working["Rejection_Reason"] = identify_rejection_reasons(working)
    working["Requires_Manual_Review"] = (working["Rejection_Reason"] != "") | flag_manual_review(working)

    # Step 6: split.
    cleaned_df, rejected_df = separate_accepted_rejected(working)

    # Quantity can be a whole-number integer once bad rows are gone.
    cleaned_df["Quantity"] = cleaned_df["Quantity"].astype("int64")

    # Step 7: verification.
    verify_no_new_duplicates(raw_df, cleaned_df)
    validate_cleaned_data(cleaned_df)

    summary_df = build_cleaning_summary(raw_df, cleaned_df, rejected_df,
                                        int(product_changed.sum()), int(date_reformatted.sum()))
    return cleaned_df, rejected_df, summary_df


def build_cleaning_summary(raw_df, cleaned_df, rejected_df,
                           products_standardised, dates_converted) -> pd.DataFrame:
    """Build a table showing what cleaning did, for documentation."""
    rows = [
        ("Records in source data", len(raw_df)),
        ("Records accepted", len(cleaned_df)),
        ("Records rejected", len(rejected_df)),
        ("Product names standardised", products_standardised),
        ("Dates converted from non-ISO format", dates_converted),
        ("Accepted records flagged for manual review", int(cleaned_df["Requires_Manual_Review"].sum())),
        ("Duplicate Transaction_IDs after cleaning", int(cleaned_df["Transaction_ID"].duplicated().sum())),
    ]
    summary = pd.DataFrame(rows, columns=["Metric", "Value"])
    # Reconciliation check: accepted + rejected must equal the source total.
    if len(cleaned_df) + len(rejected_df) != len(raw_df):
        raise ValueError("Accepted + rejected records do not add up to the source total.")
    return summary
