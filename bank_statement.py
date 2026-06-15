"""
parse_huntington.py
--------------------
Extracts the "Debit Card / POS Activity (-)" section from a Huntington Bank
PDF statement, auto-categorizes each transaction, and writes a CSV with
columns: Date, Description, Category, Amount.

Usage:
    python parse_huntington.py <path_to_pdf> [output_csv]

If output_csv is omitted, the CSV is written next to the PDF with the same
base name and a .csv extension.
"""

import re
import sys
import csv
from datetime import datetime
from pathlib import Path

import pdfplumber

# ---------------------------------------------------------------------------
# Category rules — ordered list of (pattern, category) tuples.
# Matched case-insensitively against the cleaned description.
# ---------------------------------------------------------------------------
CATEGORY_RULES = [
    # Fuel FIRST (before wholesale/grocery catch-alls)
    (r"fuel",                       "Gas"),
    (r"shell",                      "Gas"),
    (r"speedway",                   "Gas"),
    (r"marathon\s*petro",           "Gas"),
    (r"sunoco",                     "Gas"),
    (r"chevron",                    "Gas"),
    (r"exxon",                      "Gas"),
    (r"mobil",                      "Gas"),
    # Arts & Crafts
    (r"hobbylobby|hobby\s*lobby",   "Arts & Crafts"),
    (r"michaels",                   "Arts & Crafts"),
    (r"jo-?ann",                    "Arts & Crafts"),
    # Groceries / wholesale
    (r"meijer",                     "Groceries"),
    (r"wal.?mart|wm\s*supercenter|wmsupercenter", "Groceries"),
    (r"sam.?s\s*club",              "Groceries"),
    (r"target",                     "Groceries"),
    (r"holiday\s*market",           "Groceries"),
    (r"busch",                      "Groceries"),
    (r"whole\s*foods",              "Groceries"),
    (r"kroger",                     "Groceries"),
    (r"aldi",                       "Groceries"),
    (r"trader\s*joe",               "Groceries"),
    (r"bjs?\s*wholesale|bjswholesale", "Groceries"),
    # Health & Fitness
    (r"planet\s*fitness|planetfitness", "Health & Fitness"),
    (r"cvs",                        "Health & Fitness"),
    (r"walgreen",                   "Health & Fitness"),
    # Insurance / Healthcare
    (r"cigna",                      "Insurance"),
    (r"unitedhealthcare",           "Insurance"),
    (r"blue\s*cross",               "Insurance"),
    (r"aetna",                      "Insurance"),
    # Dining
    (r"mcdonald",                   "Dining"),
    (r"starbucks",                  "Dining"),
    (r"subway",                     "Dining"),
    (r"pizza",                      "Dining"),
    (r"restaurant",                 "Dining"),
    # Utilities
    (r"consumers\s*energy",         "Utilities"),
    (r"dte\s*energy",               "Utilities"),
    (r"at&t",                       "Utilities"),
    (r"comcast",                    "Utilities"),
    (r"spectrum",                   "Utilities"),
]

COMPILED_RULES = [(re.compile(p, re.IGNORECASE), cat) for p, cat in CATEGORY_RULES]

# Friendly display names for known compact store codes
DISPLAY_NAMES = {
    "WMSUPERCENTER":   "Walmart Supercenter",
    "HOBBYLOBBY":      "Hobby Lobby",
    "BJSWHOLESALE":    "BJ's Wholesale",
    "HOLIDAYMARKETO5": "Holiday Market",
    "MEIJERSTORE":     "Meijer",
    "SAMSCLUB":        "Sam's Club",
    "MICHAELSSTORES":  "Michaels",
    "PLANETFITNESSC":  "Planet Fitness",
    "CIGNAPDP":        "Cigna",
}


def categorize(description: str) -> str:
    for pattern, category in COMPILED_RULES:
        if pattern.search(description):
            return category
    return "Other"


def friendly_name(raw: str) -> str:
    """Map compact all-caps store codes to a readable name where known."""
    upper = re.sub(r"[^A-Z]", "", raw.upper())  # letters only for matching key
    for key, display in DISPLAY_NAMES.items():
        if upper.startswith(key):
            # Preserve any store number suffix from raw
            num = re.search(r"#\s*\d+", raw)
            return f"{display} {num.group()}" if num else display
    return raw


# ---------------------------------------------------------------------------
# PDF parsing
# ---------------------------------------------------------------------------

TX_RE = re.compile(
    r"^(\d{2}/\d{2})\s*PURCHASE\s*(.+?)\s*(\d{1,3}(?:,\d{3})*\.\d{2})\s*$"
)


def clean_description(raw: str) -> str:
    """
    Strip masked card numbers, city/state, and duplicate store-name tokens.
    Works on the no-space-concatenated output pdfplumber produces for this PDF.
    """
    # 1. Remove masked card number (4+ X's followed by last 4 digits)
    s = re.sub(r"X{4,}\d{4}", "", raw).strip()

    # 2. Find the smallest repeating prefix FIRST (store names are usually doubled)
    n = len(s)
    for half in range(4, n // 2 + 1):
        candidate = s[:half]
        if s[half:].startswith(candidate) and candidate.strip():
            return friendly_name(candidate.strip())

    # 3. No repeat found — strip city/state suffix and return
    s = re.sub(r"[A-Z]{2,}(?:\s*[A-Z]{2,})*\s*MI\b.*$", "", s).strip()
    return friendly_name(s)


def extract_statement_years(text: str) -> list:
    """Pull years from the statement period (handles '12/17/25 to 01/21/26' style)."""
    matches = re.findall(r"\d{2}/\d{2}/(\d{2,4})", text)
    years = []
    for m in matches:
        yr = int(m)
        if yr < 100:
            yr += 2000
        if yr not in years:
            years.append(yr)
    return sorted(years) if years else [datetime.now().year]


def infer_year(date_str: str, statement_years: list) -> str:
    month = int(date_str.split("/")[0])
    if len(statement_years) == 1:
        return f"{date_str}/{statement_years[0]}"
    # Jan dates get the later year when statement spans Dec→Jan
    if month == 1:
        return f"{date_str}/{max(statement_years)}"
    return f"{date_str}/{min(statement_years)}"


def parse_transactions(pdf_path: str) -> list:
    transactions = []
    all_text_lines = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            all_text_lines.extend(text.splitlines())

    full_text = "\n".join(all_text_lines)
    statement_years = extract_statement_years(full_text)

    in_section = False

    for line in all_text_lines:
        stripped = line.strip()

        # Section start
        if re.search(r"Debit\s*Card\s*/\s*POS\s*Activity", stripped, re.IGNORECASE):
            in_section = True
            continue

        # Section end — stop when we hit the next section header
        if in_section and re.search(
            r"(Other\s*Withdrawal|Check\s*Activity|Deposit\s*/\s*Credit|"
            r"Balance\s*Activity|StatementPeriod|Statement\s*Period)",
            stripped, re.IGNORECASE
        ):
            in_section = False
            continue

        if not in_section:
            continue

        m = TX_RE.match(stripped)
        if not m:
            continue

        date_raw   = m.group(1)
        desc_raw   = m.group(2)
        amount_raw = m.group(3)

        full_date   = infer_year(date_raw, statement_years)
        description = clean_description(desc_raw)
        amount      = float(amount_raw.replace(",", ""))
        category    = categorize(description)

        transactions.append({
            "Date":        full_date,
            "Description": description,
            "Category":    category,
            "Amount":      amount,
        })

    # Sort by date ascending
    transactions.sort(key=lambda r: datetime.strptime(r["Date"], "%m/%d/%Y"))
    return transactions


def write_csv(transactions: list, output_path: str):
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["Date", "Description", "Category", "Amount"]
        )
        writer.writeheader()
        writer.writerows(transactions)
    print(f"Wrote {len(transactions)} transactions to {output_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python parse_huntington.py <statement.pdf> [output.csv]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    csv_path = sys.argv[2] if len(sys.argv) >= 3 else str(Path(pdf_path).with_suffix(".csv"))

    transactions = parse_transactions(pdf_path)
    if not transactions:
        print("No debit card transactions found. Check that the PDF is a Huntington statement.")
        sys.exit(1)

    write_csv(transactions, csv_path)


if __name__ == "__main__":
    main()
