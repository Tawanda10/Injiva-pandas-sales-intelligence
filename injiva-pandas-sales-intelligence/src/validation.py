"""
validation.py
=============
STAGE 1 (DataFrame construction & schema validation) and
STAGE 2 (data quality investigation).

This module is split into two kinds of checks. The assessment asks us to
keep them separate:

1. STRUCTURAL validation (schema): does the table have the right shape?
   - Do all dictionary lists have the same length?
   - Are all mandatory columns present?
   - Does each column have the expected data type?

2. BUSINESS-RULE validation (data quality): are the values sensible?
   - Negative or zero quantities, missing prices, odd dates, etc.

Structural validation runs FIRST. Business rules mean nothing if the
columns they depend on do not exist.
"""

from datetime import datetime

import numpy as np
import pandas as pd

from src.source_data import COMPANY_CITIES

# ===========================================================================
# SECTION A: SCHEMA DEFINITIONS (shared constants)
# ===========================================================================
# Keeping rules in one place means every module and every test uses the
# same definitions. If a rule changes, we change it here only.

# Columns that every sales record MUST have. Without any of these we
# cannot calculate revenue or report on performance.
MANDATORY_COLUMNS = [
    "Transaction_ID", "Date", "Product", "Category", "Quantity",
    "Unit_Price", "Unit_Cost", "Salesperson", "City",
    "Payment_Method", "Discount_Percent",
]

# Expected data types for the RAW data (straight from the dictionary).
# We use general "families" (text / integer / numeric) rather than exact
# dtype names, because pandas may store text as "object" or "str"
# depending on the version.
EXPECTED_RAW_TYPES = {
    "Transaction_ID": "text",
    "Date": "text",             # raw dates are strings in mixed formats
    "Product": "text",
    "Category": "text",
    "Quantity": "integer",
    "Unit_Price": "numeric",    # float, because one value is missing (None)
    "Unit_Cost": "numeric",
    "Salesperson": "text",
    "City": "text",
    "Payment_Method": "text",
    "Discount_Percent": "numeric",
}

# Expected data types AFTER cleaning. Dates must be real datetimes.
EXPECTED_CLEAN_TYPES = {**EXPECTED_RAW_TYPES, "Date": "datetime"}

# Known business reference values (from the case study).
PRODUCT_CATEGORY_MAP = {
    "Laptop": "Computers",
    "Monitor": "Computers",
    "Smartphone": "Mobile",
    "Keyboard": "Accessories",
    "Mouse": "Accessories",
    "Printer": "Office Equipment",
}
VALID_CATEGORIES = sorted(set(PRODUCT_CATEGORY_MAP.values()))
VALID_PAYMENT_METHODS = ["Cash", "EcoCash", "Bank Transfer"]
VALID_CITIES = COMPANY_CITIES

# Date formats we accept, tried IN THIS ORDER. Each one is explicit so
# nothing is guessed.
# ASSUMPTION: "06/01/2026" means 6 January 2026 (day first), because the
# brief says every transaction is from January 2026 and Zimbabwe writes
# dates day/month/year.
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]
REPORTING_PERIOD_START = pd.Timestamp("2026-01-01")
REPORTING_PERIOD_END = pd.Timestamp("2026-01-31")

# ASSUMPTION (business policy): discounts must be between 0 and 100 %.
# Anything above 30 % is "suspicious" and needs manager approval.
MIN_DISCOUNT, MAX_DISCOUNT = 0, 100
MAX_POLICY_DISCOUNT = 30


class SchemaValidationError(ValueError):
    """Raised when the DataFrame structure is wrong (missing columns,
    wrong types, mismatched list lengths).

    A custom exception lets callers catch exactly this problem without
    using a broad ``except Exception`` that would hide other bugs.
    """


# ===========================================================================
# SECTION B: DATAFRAME CONSTRUCTION
# ===========================================================================
def check_list_lengths(data_dict: dict) -> int:
    """Check that every list in the dictionary has the same length.

    ``pd.DataFrame`` would also fail on unequal lengths, but its error
    message does not say WHICH column is wrong. This one does.

    Returns the common length (the number of records).
    """
    if not data_dict:
        raise SchemaValidationError("The source dictionary is empty.")

    lengths = {column: len(values) for column, values in data_dict.items()}
    unique_lengths = set(lengths.values())
    if len(unique_lengths) != 1:
        raise SchemaValidationError(
            f"Dictionary lists have inconsistent lengths: {lengths}"
        )
    return unique_lengths.pop()


def build_sales_dataframe(data_dict: dict) -> pd.DataFrame:
    """Turn the sales dictionary into a DataFrame after checking lengths.

    ``pd.DataFrame`` copies the data, so the source dictionary stays as
    it was.
    """
    check_list_lengths(data_dict)
    return pd.DataFrame(data_dict)


# ===========================================================================
# SECTION C: SCHEMA (STRUCTURAL) VALIDATION
# ===========================================================================
def _matches_type_family(series: pd.Series, family: str) -> bool:
    """Return True if a column's dtype belongs to the expected family."""
    if family == "text":
        return pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series)
    if family == "integer":
        return pd.api.types.is_integer_dtype(series)
    if family == "numeric":
        return pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)
    if family == "datetime":
        return pd.api.types.is_datetime64_any_dtype(series)
    raise ValueError(f"Unknown type family: {family}")


def validate_schema(df: pd.DataFrame,
                    required_columns=None,
                    expected_types=None) -> dict:
    """Reusable schema validation function.

    Checks, in order:
      1. The input really is a DataFrame.
      2. It is not empty.
      3. All mandatory COLUMNS exist. (A missing column is a structural
         error. A missing VALUE inside a column is a data-quality issue
         and is handled in Stage 2.)
      4. There are no duplicate column names.
      5. Each column has the expected data type.

    Raises ``SchemaValidationError`` with a clear message if anything is
    wrong. Otherwise returns a small report dictionary.
    """
    required_columns = required_columns or MANDATORY_COLUMNS
    expected_types = expected_types or EXPECTED_RAW_TYPES

    if not isinstance(df, pd.DataFrame):
        raise SchemaValidationError(
            f"Expected a pandas DataFrame but received {type(df).__name__}."
        )
    if df.empty:
        raise SchemaValidationError("The DataFrame has no rows.")

    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise SchemaValidationError(
            f"Missing mandatory column(s): {missing_columns}. "
            f"Columns found: {list(df.columns)}"
        )

    duplicated_columns = df.columns[df.columns.duplicated()].tolist()
    if duplicated_columns:
        raise SchemaValidationError(f"Duplicate column names: {duplicated_columns}")

    type_errors = {
        col: f"expected {family}, found {df[col].dtype}"
        for col, family in expected_types.items()
        if col in df.columns and not _matches_type_family(df[col], family)
    }
    if type_errors:
        raise SchemaValidationError(f"Data type mismatches: {type_errors}")

    return {
        "rows": len(df),
        "columns": df.shape[1],
        "missing_columns": [],
        "type_errors": {},
        "status": "PASSED",
    }


# ===========================================================================
# SECTION D: HELPER - EXPLICIT DATE PARSING
# ===========================================================================
def parse_date_value(value):
    """Parse one date string using the explicit formats in DATE_FORMATS.

    Returns a ``pd.Timestamp`` on success, or ``pd.NaT`` (Not a Time) if no
    format matches. Trying each format in turn means an unknown format is
    reported, never silently guessed.
    """
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return pd.NaT
    for date_format in DATE_FORMATS:
        try:
            return pd.Timestamp(datetime.strptime(str(value).strip(), date_format))
        except ValueError:
            continue  # this format did not match; try the next one
    return pd.NaT


# ===========================================================================
# SECTION E: DATA QUALITY INVESTIGATION (BUSINESS RULES)
# ===========================================================================
# Every rule adds rows to one list of "issues". If a rule finds nothing,
# it still adds ONE row saying "No violations found", so the report shows
# the rule was checked. This makes the report auditable.

REPORT_COLUMNS = [
    "Rule_ID", "Rule_Name", "Transaction_ID", "Affected_Column",
    "Original_Value", "Issue_Description", "Severity",
    "Recommended_Action", "Resolution_Status",
]


def _issue(rule_id, rule_name, txn, column, value, description,
           severity, action, status):
    """Build one row of the data quality report as a dictionary."""
    return {
        "Rule_ID": rule_id, "Rule_Name": rule_name, "Transaction_ID": txn,
        "Affected_Column": column, "Original_Value": value,
        "Issue_Description": description, "Severity": severity,
        "Recommended_Action": action, "Resolution_Status": status,
    }


def _pass(rule_id, rule_name, column):
    """Build the row that records 'this rule passed'."""
    return _issue(rule_id, rule_name, "ALL", column, "", "No violations found",
                  "None", "No action required", "Passed")


def missing_value_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Count and percentage of missing values for every column."""
    summary = pd.DataFrame({
        "Missing_Count": df.isna().sum(),
        "Missing_Percent": (df.isna().mean() * 100).round(2),
    })
    summary.index.name = "Column"
    return summary


def run_data_quality_checks(df: pd.DataFrame) -> pd.DataFrame:
    """Run every Stage 2 rule and return a structured Data Quality Report.

    The input DataFrame is NOT modified. We only read from it.
    Each rule uses Boolean masks (vectorised filters) rather than
    row-by-row loops wherever practical.
    """
    issues = []
    txn = df["Transaction_ID"]

    # --- R01: missing values in any column except Unit_Price ---------------
    # (Unit_Price has its own rule, R06, with a more specific action.)
    found = False
    for column in [c for c in df.columns if c != "Unit_Price"]:
        for idx in df.index[df[column].isna()]:
            found = True
            issues.append(_issue("R01", "Missing value", txn[idx], column, "",
                                 f"{column} is missing", "High",
                                 "Obtain value from source system", "Open - manual review"))
    if not found:
        issues.append(_pass("R01", "Missing value", "All except Unit_Price"))

    # --- R02: duplicate transaction identifiers ----------------------------
    # Transaction_ID is the business key. Products repeat all the time,
    # so a repeated product name is NOT a duplicate.
    dup_ids = df[txn.duplicated(keep=False)]
    if dup_ids.empty:
        issues.append(_pass("R02", "Duplicate Transaction_ID", "Transaction_ID"))
    for idx, row in dup_ids.iterrows():
        issues.append(_issue("R02", "Duplicate Transaction_ID", row["Transaction_ID"],
                             "Transaction_ID", row["Transaction_ID"],
                             "Transaction_ID appears more than once", "Critical",
                             "Investigate; keep one authoritative record", "Open - manual review"))

    # --- R03: completely duplicated records --------------------------------
    full_dups = df[df.duplicated(keep="first")]
    if full_dups.empty:
        issues.append(_pass("R03", "Fully duplicated record", "All columns"))
    for idx, row in full_dups.iterrows():
        issues.append(_issue("R03", "Fully duplicated record", row["Transaction_ID"],
                             "All columns", "", "Entire row duplicates an earlier row",
                             "High", "Remove the duplicate after confirmation",
                             "Open - manual review"))

    # Turn numeric columns into numbers. Anything that is not a number
    # becomes NaN, which lets us find non-numeric values safely.
    qty = pd.to_numeric(df["Quantity"], errors="coerce")
    price = pd.to_numeric(df["Unit_Price"], errors="coerce")
    cost = pd.to_numeric(df["Unit_Cost"], errors="coerce")
    discount = pd.to_numeric(df["Discount_Percent"], errors="coerce")

    # --- R04: negative quantities ------------------------------------------
    # A negative quantity MAY be a return or reversal, but there is no
    # return reference or link to an original sale, so we cannot confirm
    # it. We neither delete it nor count it as revenue. It goes to review.
    mask = qty < 0
    if not mask.any():
        issues.append(_pass("R04", "Negative quantity", "Quantity"))
    for idx in df.index[mask]:
        issues.append(_issue("R04", "Negative quantity", txn[idx], "Quantity", df.at[idx, "Quantity"],
                             "Negative quantity: possible return/reversal or entry error; "
                             "no link to an original sale", "High",
                             "Exclude from sales totals; confirm with Sales whether it is a return",
                             "Rejected - pending manual review"))

    # --- R05: zero quantities ----------------------------------------------
    mask = qty == 0
    if not mask.any():
        issues.append(_pass("R05", "Zero quantity", "Quantity"))
    for idx in df.index[mask]:
        issues.append(_issue("R05", "Zero quantity", txn[idx], "Quantity", df.at[idx, "Quantity"],
                             "Zero units sold: no economic transaction occurred "
                             "(possible cancelled or incomplete entry)", "Medium",
                             "Exclude from sales totals; confirm whether the sale was cancelled",
                             "Rejected - pending manual review"))

    # --- R06: missing selling prices ---------------------------------------
    # A missing price is NOT zero. Filling it with 0 or an average would
    # invent revenue, so we reject the row and ask for the real price.
    mask = df["Unit_Price"].isna()
    if not mask.any():
        issues.append(_pass("R06", "Missing selling price", "Unit_Price"))
    for idx in df.index[mask]:
        issues.append(_issue("R06", "Missing selling price", txn[idx], "Unit_Price", "None",
                             "Unit_Price is missing; revenue cannot be calculated", "High",
                             "Do not impute; obtain actual invoice price from Finance",
                             "Rejected - pending manual review"))

    # --- R07: invalid unit prices (present but non-numeric or <= 0) --------
    mask = df["Unit_Price"].notna() & (price.isna() | (price <= 0))
    if not mask.any():
        issues.append(_pass("R07", "Invalid unit price", "Unit_Price"))
    for idx in df.index[mask]:
        issues.append(_issue("R07", "Invalid unit price", txn[idx], "Unit_Price",
                             df.at[idx, "Unit_Price"], "Unit_Price is non-numeric or not positive",
                             "High", "Correct price from source system",
                             "Rejected - pending manual review"))

    # --- R08: invalid unit costs -------------------------------------------
    mask = cost.isna() | (cost <= 0)
    if not mask.any():
        issues.append(_pass("R08", "Invalid unit cost", "Unit_Cost"))
    for idx in df.index[mask]:
        issues.append(_issue("R08", "Invalid unit cost", txn[idx], "Unit_Cost",
                             df.at[idx, "Unit_Cost"], "Unit_Cost is missing, non-numeric or not positive",
                             "High", "Correct cost from procurement records",
                             "Rejected - pending manual review"))

    # --- R09: selling price below cost (unusual, not necessarily wrong) ----
    mask = price.notna() & cost.notna() & (price < cost)
    if not mask.any():
        issues.append(_pass("R09", "Unit price below unit cost", "Unit_Price"))
    for idx in df.index[mask]:
        issues.append(_issue("R09", "Unit price below unit cost", txn[idx], "Unit_Price",
                             df.at[idx, "Unit_Price"], "Item sold below cost (possible clearance)",
                             "Medium", "Confirm pricing with Sales manager", "Accepted - flagged"))

    # --- R10: inconsistent product names -----------------------------------
    # The standard form is Title Case with no extra spaces, e.g. "Laptop".
    standard_product = df["Product"].astype(str).str.strip().str.title()
    mask = df["Product"].astype(str) != standard_product
    if not mask.any():
        issues.append(_pass("R10", "Inconsistent product name", "Product"))
    for idx in df.index[mask]:
        issues.append(_issue("R10", "Inconsistent product name", txn[idx], "Product",
                             df.at[idx, "Product"],
                             f"Non-standard casing; standard form is '{standard_product[idx]}'",
                             "Low", "Standardise to Title Case",
                             "Resolved - standardised during cleaning"))
    unknown_products = ~standard_product.isin(PRODUCT_CATEGORY_MAP.keys())
    for idx in df.index[unknown_products]:
        issues.append(_issue("R10", "Unknown product", txn[idx], "Product", df.at[idx, "Product"],
                             "Product not in the reference product list", "High",
                             "Add product to reference data or correct entry", "Open - manual review"))

    # --- R11: inconsistent categories --------------------------------------
    mask = ~df["Category"].isin(VALID_CATEGORIES)
    if not mask.any():
        issues.append(_pass("R11", "Inconsistent category", "Category"))
    for idx in df.index[mask]:
        issues.append(_issue("R11", "Inconsistent category", txn[idx], "Category",
                             df.at[idx, "Category"], "Category not in the approved list",
                             "Medium", "Map to an approved category", "Open - manual review"))

    # --- R12: invalid or non-standard dates --------------------------------
    parsed_dates = df["Date"].apply(parse_date_value)
    iso_dates = pd.to_datetime(df["Date"], format="%Y-%m-%d", errors="coerce")
    unparseable = parsed_dates.isna()
    non_iso = parsed_dates.notna() & iso_dates.isna()
    outside_period = parsed_dates.notna() & ~parsed_dates.between(
        REPORTING_PERIOD_START, REPORTING_PERIOD_END)
    if not (unparseable | non_iso | outside_period).any():
        issues.append(_pass("R12", "Invalid date", "Date"))
    for idx in df.index[unparseable]:
        issues.append(_issue("R12", "Invalid date", txn[idx], "Date", df.at[idx, "Date"],
                             "Date does not match any accepted format", "High",
                             "Obtain correct date from source system", "Rejected - pending manual review"))
    for idx in df.index[non_iso]:
        issues.append(_issue("R12", "Non-standard date format", txn[idx], "Date", df.at[idx, "Date"],
                             f"Date not in ISO format (YYYY-MM-DD); interpreted day-first as "
                             f"{parsed_dates[idx].date()}", "Low",
                             "Convert with explicit day-first format", "Resolved - converted during cleaning"))
    for idx in df.index[outside_period]:
        issues.append(_issue("R12", "Date outside reporting period", txn[idx], "Date", df.at[idx, "Date"],
                             "Date falls outside January 2026", "Medium",
                             "Confirm the transaction date", "Open - manual review"))

    # --- R13: incorrect data types (column level) --------------------------
    # The raw Date column is text. Dates must be datetime64 for any
    # time-based work, so this is reported once for the whole column.
    type_issue_found = False
    for column, family in EXPECTED_CLEAN_TYPES.items():
        if column in df.columns and not _matches_type_family(df[column], family):
            type_issue_found = True
            issues.append(_issue("R13", "Incorrect data type", "ALL", column, str(df[column].dtype),
                                 f"Column stored as {df[column].dtype}; expected {family}", "Medium",
                                 f"Convert column to {family}", "Resolved - converted during cleaning"))
    # Unit_Price became float64 because one value is None. That is fine
    # for money, but we note it so a reviewer knows why it is not integer.
    if pd.api.types.is_float_dtype(df["Unit_Price"]) and df["Unit_Price"].isna().any():
        type_issue_found = True
        issues.append(_issue("R13", "Inferred data type", "ALL", "Unit_Price", str(df["Unit_Price"].dtype),
                             "Pandas inferred float64 because a value is missing (None -> NaN)",
                             "Low", "Keep as float for currency; handle missing value via R06",
                             "Accepted - documented"))
    if not type_issue_found:
        issues.append(_pass("R13", "Incorrect data type", "All columns"))

    # --- R14: suspicious discount percentages ------------------------------
    out_of_range = discount.isna() | (discount < MIN_DISCOUNT) | (discount > MAX_DISCOUNT)
    above_policy = ~out_of_range & (discount > MAX_POLICY_DISCOUNT)
    if not (out_of_range | above_policy).any():
        issues.append(_pass("R14", "Suspicious discount", "Discount_Percent"))
    for idx in df.index[out_of_range]:
        issues.append(_issue("R14", "Invalid discount", txn[idx], "Discount_Percent",
                             df.at[idx, "Discount_Percent"], "Discount outside 0-100 %", "High",
                             "Correct the discount", "Rejected - pending manual review"))
    for idx in df.index[above_policy]:
        issues.append(_issue("R14", "Suspicious discount", txn[idx], "Discount_Percent",
                             df.at[idx, "Discount_Percent"],
                             f"Discount above {MAX_POLICY_DISCOUNT}% policy limit", "Medium",
                             "Confirm manager approval", "Open - manual review"))

    # --- R15: unexpected product-category relationships --------------------
    expected_category = standard_product.map(PRODUCT_CATEGORY_MAP)
    mask = expected_category.notna() & (df["Category"] != expected_category)
    if not mask.any():
        issues.append(_pass("R15", "Unexpected product-category pair", "Category"))
    for idx in df.index[mask]:
        issues.append(_issue("R15", "Unexpected product-category pair", txn[idx], "Category",
                             df.at[idx, "Category"],
                             f"{standard_product[idx]} should be in '{expected_category[idx]}'",
                             "Medium", "Correct the category", "Open - manual review"))

    # --- R16 / R17: unknown cities and payment methods ---------------------
    for rule_id, column, valid in [("R16", "City", VALID_CITIES),
                                   ("R17", "Payment_Method", VALID_PAYMENT_METHODS)]:
        mask = ~df[column].isin(valid)
        if not mask.any():
            issues.append(_pass(rule_id, f"Unknown {column}", column))
        for idx in df.index[mask]:
            issues.append(_issue(rule_id, f"Unknown {column}", txn[idx], column, df.at[idx, column],
                                 f"{column} not in approved list", "Medium",
                                 "Correct the value", "Open - manual review"))

    report = pd.DataFrame(issues, columns=REPORT_COLUMNS)
    # Original_Value mixes numbers and text, so we store it as text.
    report["Original_Value"] = report["Original_Value"].astype(str)
    return report


# ===========================================================================
# SECTION F: VALIDATION OF THE CLEANED DATASET (run before export)
# ===========================================================================
def validate_cleaned_data(df: pd.DataFrame) -> None:
    """Check that the cleaned (accepted) data meets every business rule.

    This runs AFTER cleaning and BEFORE exporting, so invalid data is never
    written to the final CSV files. Raises ``ValueError`` and lists every
    problem it finds.
    """
    validate_schema(df, expected_types=EXPECTED_CLEAN_TYPES)
    problems = []
    if df["Transaction_ID"].duplicated().any():
        problems.append("duplicate Transaction_ID values")
    if df[MANDATORY_COLUMNS].isna().any().any():
        problems.append("missing values in mandatory columns")
    if (df["Quantity"] <= 0).any():
        problems.append("non-positive quantities")
    if (df["Unit_Price"] <= 0).any():
        problems.append("non-positive unit prices")
    if (df["Unit_Cost"] <= 0).any():
        problems.append("non-positive unit costs")
    if (~df["Discount_Percent"].between(MIN_DISCOUNT, MAX_DISCOUNT)).any():
        problems.append("discounts outside 0-100 %")
    if (~df["Product"].isin(PRODUCT_CATEGORY_MAP.keys())).any():
        problems.append("non-standard product names")
    if (~df["Date"].between(REPORTING_PERIOD_START, REPORTING_PERIOD_END)).any():
        problems.append("dates outside the reporting period")
    if problems:
        raise ValueError("Cleaned data failed validation: " + "; ".join(problems))
