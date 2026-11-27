"""
source_data.py
==============
ORIGINAL SOURCE DATASET (read-only).

This file keeps the original ``sales_data`` dictionary exactly as it was
supplied in assessment INJIVA-DS-DA-PANDAS-001.

Why a separate file?
--------------------
* The assessment says the original dictionary must stay available for
  auditing and comparison. Keeping it in its own module means no other
  code changes it by accident.
* Other modules never use ``sales_data`` directly. They call
  ``get_sales_data()``, which returns a *deep copy*. Changing the copy can
  never change the original.

DO NOT EDIT THE VALUES BELOW: the errors in them are deliberate and must
stay visible so the data quality checks can find them.
"""

import copy

# ---------------------------------------------------------------------------
# The original dictionary (copied verbatim from the assessment brief)
# ---------------------------------------------------------------------------
sales_data = {
    "Transaction_ID": [
        "TX001", "TX002", "TX003", "TX004",
        "TX005", "TX006", "TX007", "TX008",
        "TX009", "TX010", "TX011", "TX012",
        "TX013", "TX014", "TX015", "TX016",
        "TX017", "TX018", "TX019", "TX020"
    ],
    "Date": [
        "2026-01-05", "06/01/2026", "2026-01-07",
        "2026-01-08", "09-01-2026", "2026-01-10",
        "2026-01-11", "12/01/2026", "2026-01-13",
        "2026-01-14", "2026-01-15", "16/01/2026",
        "2026-01-17", "2026-01-18", "19-01-2026",
        "2026-01-20", "2026-01-21", "2026-01-22",
        "2026-01-23", "2026-01-24"
    ],
    "Product": [
        "Laptop", "Smartphone", "keyboard",
        "Monitor", "Printer", "LAPTOP",
        "Mouse", "Smartphone", "monitor",
        "Keyboard", "Laptop", "Printer",
        "Mouse", "Smartphone", "Laptop",
        "Monitor", "Keyboard", "Printer",
        "Smartphone", "Mouse"
    ],
    "Category": [
        "Computers", "Mobile", "Accessories",
        "Computers", "Office Equipment",
        "Computers", "Accessories", "Mobile",
        "Computers", "Accessories",
        "Computers", "Office Equipment",
        "Accessories", "Mobile", "Computers",
        "Computers", "Accessories",
        "Office Equipment", "Mobile",
        "Accessories"
    ],
    "Quantity": [
        2, 5, 10, 3, 2, 1, 15, 4, -2, 8,
        3, 2, 12, 5, 0, 4, 9, 2, 6, 20
    ],
    "Unit_Price": [
        650, 300, 25, 180, 220,
        700, 15, 320, 200, 30,
        680, None, 18, 310, 670,
        190, 28, 230, 330, 15
    ],
    "Unit_Cost": [
        500, 220, 12, 130, 160,
        520, 7, 240, 145, 14,
        510, 165, 8, 235, 505,
        140, 13, 170, 250, 7
    ],
    "Salesperson": [
        "John", "Mary", "Peter", "John",
        "Sarah", "Mary", "Peter", "Sarah",
        "John", "Mary", "John", "Sarah",
        "Peter", "Mary", "John", "Sarah",
        "Peter", "Mary", "Sarah", "Peter"
    ],
    "City": [
        "Bulawayo", "Harare", "Gweru",
        "Bulawayo", "Mutare", "Harare",
        "Gweru", "Mutare", "Bulawayo",
        "Harare", "Bulawayo", "Mutare",
        "Gweru", "Harare", "Bulawayo",
        "Mutare", "Gweru", "Harare",
        "Mutare", "Gweru"
    ],
    "Payment_Method": [
        "Cash", "EcoCash", "Bank Transfer",
        "Cash", "EcoCash", "Bank Transfer",
        "Cash", "EcoCash", "Cash",
        "Bank Transfer", "Cash", "EcoCash",
        "Cash", "Bank Transfer", "Cash",
        "EcoCash", "Cash", "Bank Transfer",
        "EcoCash", "Cash"
    ],
    "Discount_Percent": [
        0, 5, 0, 10, 0, 5, 0, 10, 0, 0,
        5, 0, 0, 5, 10, 0, 0, 5, 10, 0
    ]
}

# The company operates in these five cities (from the business case).
# Masvingo has no rows in the sample. That does NOT mean Masvingo made zero
# sales; it only means the sample has no records for it.
COMPANY_CITIES = ["Bulawayo", "Harare", "Gweru", "Mutare", "Masvingo"]


def get_sales_data() -> dict:
    """Return an independent deep copy of the original dictionary.

    ``copy.deepcopy`` copies the dictionary AND every list inside it, so
    changing the returned object can never change ``sales_data``.
    """
    return copy.deepcopy(sales_data)
