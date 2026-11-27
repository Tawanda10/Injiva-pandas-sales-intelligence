# ZimTech Retail Holdings: Sales Performance & Data Quality Report

**Prepared for:** Finance, Operations and Executive Management
**Prepared by:** Trainee Data Engineer / Data Analyst, INJIVA Digital Systems Data & Analytics
**Assessment reference:** INJIVA-DS-DA-PANDAS-001
**Data period:** 5–24 January 2026 (20 source transactions, USD)

> All figures in this report come from the CSV files in `data/` produced by `python -m src.pipeline`.
> **Facts** are shown as figures. **Interpretations** and **recommendations** are labelled as such.

---

## 1. Executive Summary

| Measure | Value |
|---|---|
| Source transactions | 20 |
| Valid (accepted) transactions | 17 |
| Rejected transactions | 3 (TX009, TX012, TX015) |
| Total units sold | 111 |
| Gross revenue (before discount) | $14,033.00 |
| Discounts given | $692.50 |
| **Net revenue** | **$13,340.50** |
| Total cost | $10,085.00 |
| **Gross profit** | **$3,255.50** |
| **Overall gross profit margin** | **24.40 %** |
| Average transaction value | $784.74 |
| Loss-making transactions | 0 |

**Key messages**
1. Smartphones and laptops bring in **73 %** of revenue but have the **lowest margins** (18.8 % and 21.9 %).
2. Accessories (keyboards and mice) bring in only 11 % of revenue but earn **53 % margins**, the most profitable products per dollar sold.
3. Harare (Mary) leads on revenue and profit. Gweru (Peter) has the lowest revenue but the highest margin.
4. Discounts cost **$692.50**, equal to **21 % of gross profit**. Most of this was on smartphones.
5. Three records could not be used and need follow-up. **Masvingo has no records** in the sample, so its performance is unknown.

---

## 2. Data Quality Findings

Source: `data/data_quality_report.csv` (17 rules checked; 11 specific findings; 11 rules passed with no violations).

| Issue | Records | Severity | Action taken |
|---|---|---|---|
| Negative quantity (−2) | TX009 | High | **Rejected**: possible return, but no link to an original sale |
| Missing unit price | TX012 | High | **Rejected**: price not imputed |
| Zero quantity | TX015 | Medium | **Rejected**: no goods sold |
| Product name in wrong case (`keyboard`, `LAPTOP`, `monitor`) | TX003, TX006, TX009 | Low | Standardised to Title Case |
| Non-ISO date formats (`06/01/2026`, `09-01-2026`, …) | TX002, TX005, TX008, TX012, TX015 | Low | Converted using explicit day-first formats |
| Date column stored as text | All | Medium | Converted to datetime |

**No violations** were found for: duplicate transaction IDs, duplicate rows, invalid costs, prices below cost,
invalid categories, suspicious discounts, product-category mismatches, unknown cities or unknown payment methods.

### Financial impact of rejected records (not included in any total)

| Record | Issue | Possible impact if confirmed |
|---|---|---|
| TX009 | Monitor, −2 units at $200 | If it is a return: **−$400.00** revenue and −$110.00 gross profit |
| TX012 | Printer, 2 units, no price | At other observed Printer prices ($220–$230): **+$440 to +$460** revenue (estimate only; not used) |
| TX015 | Laptop, 0 units | $0.00, no economic effect |

*Interpretation:* if all records were resolved as above, net revenue would change by between +$40 and +$60
(about 0.3 %). The headline conclusions would not change.

---

## 3. Revenue and Profitability Analysis

- Gross revenue $14,033.00 − discounts $692.50 = **net revenue $13,340.50** (discounts = 4.9 % of gross revenue).
- Net revenue $13,340.50 − cost $10,085.00 = **gross profit $3,255.50**.
- Overall margin = $3,255.50 ÷ $13,340.50 = **24.40 %**, calculated from totals. (The average of the 17 transaction margins is 32.8 %. That figure is misleading because small, high-margin accessory sales count as much as large laptop sales.)
- Discounted transactions (10) generated $9,357.50 revenue; undiscounted transactions (7) generated $3,983.00.
- Gross profit is **not** net profit: overheads (rent, salaries, logistics) are not in the data.

**Revenue by category**

| Category | Units | Net revenue | Share | Gross profit | Margin | Avg discount |
|---|---|---|---|---|---|---|
| Mobile | 20 | $5,831.50 | 43.7 % | $1,096.50 | 18.8 % | 7.5 % |
| Computers | 13 | $5,149.00 | 38.6 % | $1,149.00 | 22.3 % | 4.0 % |
| Accessories | 74 | $1,483.00 | 11.1 % | $793.00 | 53.5 % | 0.0 % |
| Office Equipment | 4 | $877.00 | 6.6 % | $217.00 | 24.7 % | 2.5 % |

Top 3 categories by gross profit: **Computers ($1,149.00), Mobile ($1,096.50), Accessories ($793.00)**.

**Time trend (fact):** 5–14 Jan revenue was $6,183.00; 15–24 Jan revenue was $7,157.50 (**+15.8 %**). Both periods are 10 calendar days.
Highest day: 15 Jan ($1,938.00, TX011 laptops). Lowest positive day: 17 Jan ($216.00).
*Interpretation:* with only 8–9 transactions per period, this rise could easily be random variation and is not evidence of a trend.

---

## 4. Product Performance Findings

Source: `data/product_performance.csv`

| Product | Net revenue | Gross profit | Margin | Segment |
|---|---|---|---|---|
| Smartphone | $5,831.50 | $1,096.50 | 18.8 % | Revenue driver (low margin) |
| Laptop | $3,903.00 | $853.00 | 21.9 % | Revenue driver (low margin) |
| Monitor | $1,246.00 | $296.00 | 23.8 % | Underperformer |
| Printer | $877.00 | $217.00 | 24.7 % | Margin niche (low revenue) |
| Keyboard | $742.00 | $393.00 | 53.0 % | Margin niche (low revenue) |
| Mouse | $741.00 | $400.00 | 54.0 % | Margin niche (low revenue) |

- Smartphone is both the highest-revenue and the most profitable product in dollars.
- Smartphone, Laptop and Monitor have **below-average margins** (below 24.40 %).
- Six transactions have above-average revenue but below-average margin. Four are smartphones, and the lowest-margin sales (TX019 15.8 %, TX008 16.7 %) both had a 10 % discount.
- Mice earn more gross profit ($400) than printers ($217) or monitors ($296), despite low prices.

---

## 5. City-Level Performance Findings

Source: `data/city_performance.csv`

| City | Transactions | Net revenue | Share | Gross profit | Margin |
|---|---|---|---|---|---|
| Harare | 5 | $4,239.50 | 31.8 % | $992.50 | 23.4 % |
| Mutare | 4 | $4,134.00 | 31.0 % | $794.00 | 19.2 % |
| Bulawayo | 3 | $3,724.00 | 27.9 % | $804.00 | 21.6 % |
| Gweru | 5 | $1,243.00 | 9.3 % | $665.00 | **53.5 %** |
| Masvingo | – | *unknown* | – | *unknown* | – |

- Harare is the highest-revenue and most profitable city.
- Gweru sold only accessories (66 units), which explains its low revenue but very high margin.
- **Masvingo:** no records in the sample. This is a data coverage gap, **not** evidence of zero sales.

---

## 6. Salesperson Performance Findings

Source: `data/salesperson_performance.csv`

| Salesperson | City | Net revenue | Gross profit | Margin | Class |
|---|---|---|---|---|---|
| Mary | Harare | $4,239.50 | $992.50 | 23.4 % | Strong |
| Sarah | Mutare | $4,134.00 | $794.00 | 19.2 % | Mixed |
| John | Bulawayo | $3,724.00 | $804.00 | 21.6 % | Mixed |
| Peter | Gweru | $1,243.00 | $665.00 | 53.5 % | Develop (on revenue) |

- Average revenue per salesperson: $3,335.13. Peter is the only one below it.
- Sarah and John give the highest average discount (5 %). Sarah has the lowest margin (19.2 %), mainly from two 10 % smartphone discounts.
- **Caution (correlation ≠ causation):** each salesperson works in exactly one city, so person and market effects
  cannot be separated. Peter's low revenue reflects the products he sold (accessories only), not necessarily his ability.

---

## 7. Actionable Recommendations

1. **Tighten smartphone discounting.** *(Evidence: smartphones account for $478.50 of the $692.50 discounts; the 10 % discounts on TX008 and TX019 cut those sales to margins of 16.7 % and 15.8 %.)* Require manager approval for smartphone discounts above 5 %. Applied to TX008 and TX019, this would have kept about **$163** more gross profit.
2. **Cross-sell accessories with every laptop and smartphone.** *(Evidence: accessory margin 53.5 % vs 18.8 % for mobile.)* Adding one $28 keyboard (cost $13) to each of the 7 laptop and smartphone sales would add about **$105 gross profit** (+3 %).
3. **Expand Peter's product mix in Gweru.** *(Evidence: Gweru recorded only accessory sales.)* Pilot laptop and smartphone stock in Gweru, then review revenue after one month before judging performance.
4. **Fix the data at source.** *(Evidence: 8 of 20 records had a quality issue.)* Use dropdown product lists, one date format (YYYY-MM-DD) and mandatory price fields in the point-of-sale system, and record returns with a reference to the original sale.
5. **Resolve the three rejected records within 5 working days.** Finance to confirm TX012's invoice price. Sales to confirm whether TX009 is a return (−$400 revenue) and whether TX015 was cancelled.
6. **Obtain Masvingo and full-month data before any branch decision.** *(Evidence: 0 Masvingo records; only 5–24 Jan covered.)* Re-run this pipeline on complete data; it needs no code changes.

---

## 8. Dataset Limitations and Assumptions

- **Small sample:** 17 valid transactions. One large order (for example TX011, $1,938, 14.5 % of revenue) can change rankings. All conclusions are indicative.
- **Coverage:** only 5–24 January; no Masvingo records; days 1–4 and 25–31 January have no data and are treated as unknown, not zero.
- **Confounding:** salesperson and city are perfectly linked.
- **Assumptions:** slashed and dashed dates are day-first; missing prices are not imputed; negative or zero quantities are excluded pending confirmation; discounts over 30 % would need approval (none occurred).
- **Gross, not net, profit:** no overhead data.

---

## 9. Technical Implementation Summary

| Component | File | Responsibility |
|---|---|---|
| Source data | `src/source_data.py` | Original dictionary (read-only); `get_sales_data()` returns a deep copy |
| Validation | `src/validation.py` | Schema checks, 17 data quality rules, final validation before export |
| Cleaning | `src/cleaning.py` | Standardisation, explicit date parsing, accept/reject split with audit trail |
| Analytics | `src/analytics.py` | Financial columns, performance, time series, segmentation, merges, BI |
| Pipeline | `src/pipeline.py` | Runs every step and exports CSVs (relative paths) |
| Tests | `tests/test_sales_pipeline.py` | 21 automated tests (pytest), including deliberately invalid records |
| Notebook | `notebooks/sales_analysis.ipynb` | Stage-by-stage walkthrough with commentary |

Techniques: vectorised arithmetic, `groupby/agg/transform`, `rank(method="min")`, `nlargest`, `query`,
Boolean indexing, `np.select`, calendar vs transaction rolling windows, `merge(validate="many_to_one", indicator=True)`,
`pivot_table(margins=True)`, and reconciliation of every grouped total.

---

## 10. Reproduction Instructions

```bash
git clone https://github.com/<your-username>/injiva-pandas-sales-intelligence.git
cd injiva-pandas-sales-intelligence
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m src.pipeline        # regenerates every CSV in data/
python -m pytest -v           # runs the 21 tests
jupyter lab notebooks/sales_analysis.ipynb   # optional walkthrough
```
