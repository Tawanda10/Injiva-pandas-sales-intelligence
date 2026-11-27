# Git & GitHub Guide (Stage 13)

This guide is the step-by-step workflow for building this repository with a genuine commit history,
a `feature/data-cleaning` branch and a merged Pull Request.

> **Tip:** unzip the finished project into a separate folder (for example `Downloads/solution/`). Then build
> your real repository by copying files in **one stage at a time**. Read and run each file before you commit
> it, so you can explain it in your review.

---

## 0. The four "places" your work lives

| Place | What it is | Commands that move work |
|---|---|---|
| **Working directory** | The files you see and edit in VS Code | (you edit files) |
| **Staging area** | A "shopping basket" of changes for the next commit | `git add`, `git restore --staged` |
| **Local repository** | Your saved history (commits) on your computer | `git commit` |
| **Remote repository** | The copy on GitHub | `git push`, `git fetch`, `git pull` |

---

## Part A: Repository initialisation

```bash
# 1. Create the project folder and open it in VS Code
mkdir injiva-pandas-sales-intelligence
cd injiva-pandas-sales-intelligence
code .

# 2. Start tracking with Git
git init
git branch -M main                 # name the main branch "main"

# 3. Create the folder structure (Git ignores empty folders, so add a .gitkeep)
mkdir data notebooks src tests reports
touch data/.gitkeep notebooks/.gitkeep tests/.gitkeep reports/.gitkeep
# Windows PowerShell alternative to touch:  New-Item data/.gitkeep -ItemType File

# 4. Copy in .gitignore, README.md, requirements.txt, pytest.ini, GIT_GUIDE.md and an empty src/__init__.py

# 5. Check, stage and commit
git status                         # red = not staged
git add .
git status                         # green = staged
git commit -m "Initialise project structure and documentation"
```

**Create the GitHub repository:** on github.com go to **New repository**, name it `injiva-pandas-sales-intelligence`,
and do **not** tick "Add README" (you already have one). Then:

```bash
git remote add origin https://github.com/<your-username>/injiva-pandas-sales-intelligence.git
git remote -v                      # shows the fetch/push URLs
git push -u origin main            # -u remembers origin/main for future pushes
```

Refresh the GitHub page and confirm that the files are there.

---

## Part C: Commit plan (at least 8 meaningful commits)

Copy the listed files, run the check, then commit. Use `git diff` **before** `git add` to review what changed.

| # | Branch | Files to add | Check before committing | Commit message |
|---|---|---|---|---|
| 1 | main | .gitignore, README, requirements, pytest.ini, GIT_GUIDE, src/\_\_init\_\_.py | `git status` | `Initialise project structure and documentation` |
| 2 | main | `src/source_data.py` | `python -c "from src.source_data import sales_data; print(len(sales_data))"` | `Add original sales dictionary as read-only source data` |
| 3 | main | `src/validation.py` | `python -c "from src import validation"` | `Implement schema validation and data quality rules` |
| 4 | main | `data/data_quality_report.csv` (run pipeline later, or add after commit 8) | open the CSV | `Add data quality assessment report` |
| 5 | **feature/data-cleaning** | `src/cleaning.py` | see Part D | `Implement transaction cleaning with audit trail` |
| 6 | main | `src/analytics.py` | `python -c "from src import analytics"` | `Add financial calculations and sales analytics` |
| 7 | main | `tests/test_sales_pipeline.py` | `python -m pytest -v` | `Add automated validation and financial tests` |
| 8 | main | `src/pipeline.py`, all `data/*.csv` | `python -m src.pipeline` | `Add reusable pipeline and export CSV outputs` |
| 9 | main | `notebooks/sales_analysis.ipynb` | Restart & Run All | `Add stage-by-stage analysis notebook` |
| 10 | main | `reports/management_report.md` | figures match CSVs | `Complete management report` |

After each commit: `git push`. Use `git log --oneline` to see your history.

> Commit 4 depends on code from later commits. If you prefer, skip it and include the CSV in commit 8.
> You will still have more than 8 commits.

---

## Part D: Branch and Pull Request (`feature/data-cleaning`)

```bash
git switch main
git pull                                   # make sure main is up to date
git switch -c feature/data-cleaning        # create AND switch to the new branch
git branch                                 # * shows the current branch

# copy in src/cleaning.py, then test it:
python -c "from src.cleaning import clean_sales_data; from src.validation import build_sales_dataframe; from src.source_data import get_sales_data; c,r,s=clean_sales_data(build_sales_dataframe(get_sales_data())); print(s)"

git diff                                   # nothing yet? new files show after 'git add'
git add src/cleaning.py
git diff --staged                          # review exactly what will be committed
git commit -m "Implement transaction cleaning with audit trail"
git push -u origin feature/data-cleaning
```

On GitHub:
1. Click **Compare & pull request**. Make sure **base: `main`** ← **compare: `feature/data-cleaning`**.
2. Title: `Add data cleaning module`
3. Description (example):
   ```
   ## Changes
   - Standardises product names to Title Case
   - Parses dates with explicit formats (day-first for DD/MM/YYYY and DD-MM-YYYY)
   - Rejects TX009 (negative qty), TX012 (missing price), TX015 (zero qty) with reasons
   - Keeps Original_Product / Original_Date and Cleaning_Notes as an audit trail
   - Verifies that no duplicates were introduced and validates cleaned data

   ## Testing
   - Ran clean_sales_data on source data: 17 accepted, 3 rejected, 20 total
   ```
4. Open the **Files changed** tab and review the code (add a comment on one line if you like).
5. Click **Merge pull request**, then **Confirm merge**. Do not delete the PR; it stays in the history.

Back in your terminal:

```bash
git switch main
git fetch                  # download remote changes WITHOUT applying them
git pull                   # download AND merge them into main
git log --oneline --graph  # you will see the merge
```

---

## Part B: Demonstrating the remaining commands

```bash
# git restore: undo an unwanted change in the working directory
echo "# mistake" >> README.md
git diff                   # shows the added line
git restore README.md      # file goes back to the last committed version

# git restore --staged: take a file back out of the staging area
git add README.md
git restore --staged README.md

# git clone: prove the repo works on a "fresh" computer
cd ..
git clone https://github.com/<your-username>/injiva-pandas-sales-intelligence.git clone-test
cd clone-test
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q
```

---

## Part E: Security checklist (before every push)

- [ ] `git status` shows no `.venv/`, `__pycache__/` or `.ipynb_checkpoints/`.
- [ ] No passwords, tokens or `.env` files are staged.
- [ ] If you log in to GitHub from the terminal, use a **Personal Access Token** or GitHub CLI, and never put it in a file in the repository.
- [ ] Never use `git push --force` on `main`.
