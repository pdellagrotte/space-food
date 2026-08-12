# Credit Offer Evaluator

A small, dependency-free Python program that ranks credit-card and bank offers from a JSON file and writes an Excel-friendly CSV.

It values:

- American Express Membership Rewards at 1.5 cents per point.
- Chase Ultimate Rewards at 2 cents per point.
- All other points at 1 cent per point.

It excludes offers that are expired, stale, already applied for, already held, previously bonused, or known to be ineligible. Remaining offers are ranked by estimated first-year value after the annual fee.

## Run on Windows

1. Install Python 3.11 or newer. One option is:

   ```powershell
   winget install Python.Python.3.12
   ```

2. Open PowerShell and verify Python:

   ```powershell
   py --version
   ```

3. Clone the repository, then change into this folder:

   ```powershell
   git clone <YOUR-REPOSITORY-URL>
   cd <YOUR-REPOSITORY-FOLDER>\credit-offer-evaluator
   ```

4. Copy the sample input and edit the copy with your own offers:

   ```powershell
   Copy-Item offers.sample.json offers.json
   notepad offers.json
   ```

5. Run the evaluator:

   ```powershell
   py credit_offer_evaluator.py offers.json --output offer_results.csv
   ```

6. Open `offer_results.csv` in Excel. Focus first on `CONSIDER`, then manually check `REVIEW` rows.

To reproduce an evaluation for a specific date:

```powershell
py credit_offer_evaluator.py offers.json --output offer_results.csv --as-of 2026-08-11
```

## Input notes

- Use `amex_membership_rewards` only for Membership Rewards points.
- Use `chase_ultimate_rewards` only for Ultimate Rewards points. Hotel and airline points issued on a Chase card remain `other`.
- Set `eligible` to `true`, `false`, or `"unknown"`.
- Set `metadata_complete` to `false` when the email does not show the fee, deadline, or qualifying requirement. The program will mark it `REVIEW`.
- Do not store private Gmail links in a public repository. Keep your real `offers.json` local or add it to `.gitignore`.
