"""
parse_huntington.py
--------------------
Extracts transactions from Huntington Bank PDF statements, auto-categorizes 
each transaction, and writes a combined CSV with columns: Date, Description, 
Category, Amount, Type.

Usage:
    python bank_statement.py <directory_path> [output_csv]

If output_csv is omitted, defaults to "combined_transactions.csv" in the 
current directory.
"""

import re
import sys
import csv
from datetime import datetime
from pathlib import Path

import pdfplumber

# ---------------------------------------------------------------------------
# Category rules — ordered list of (pattern, category) tuples.
# ---------------------------------------------------------------------------
CATEGORY_RULES = [
    # Income / Credits
    (r"ssa\s*treas|social\s*security",  "Income - Social Security"),
    (r"deposit",                         "Income - Deposit"),
    (r"merchandise\s*ret",               "Income - Return"),
    # Subscriptions / Memberships
    (r"planet\s*fitness|planetfitness",  "Subscriptions"),
    (r"unitedhealthcare",                "Insurance"),
    (r"cigna",                           "Insurance"),
    (r"blue\s*cross",                    "Insurance"),
    (r"aetna",                           "Insurance"),
    # Fuel FIRST (before wholesale/grocery catch-alls)
    (r"fuel",                            "Gas"),
    (r"shell",                           "Gas"),
    (r"speedway",                        "Gas"),
    (r"marathon\s*petro",                "Gas"),
    (r"sunoco",                          "Gas"),
    (r"chevron",                         "Gas"),
    (r"exxon",                           "Gas"),
    (r"mobil",                           "Gas"),
    # Medical / Dental
    (r"dental|dentistry",                "Medical - Dental"),
    (r"dermatology",                     "Medical - Specialist"),
    # Arts & Crafts
    (r"hobbylobby|hobby\s*lobby",        "Arts & Crafts"),
    (r"michaels",                        "Arts & Crafts"),
    (r"jo-?ann",                         "Arts & Crafts"),
    # Groceries / wholesale
    (r"meijer",                          "Groceries"),
    (r"wal.?mart|wm\s*supercenter|wmsupercenter", "Groceries"),
    (r"sam.?s\s*club",                   "Groceries"),
    (r"target",                          "Groceries"),
    (r"holiday\s*market",                "Groceries"),
    (r"fresh\s*thyme",                   "Groceries"),
    (r"busch",                           "Groceries"),
    (r"whole\s*foods",                   "Groceries"),
    (r"kroger",                          "Groceries"),
    (r"aldi",                            "Groceries"),
    (r"trader\s*joe",                    "Groceries"),
    (r"bjs?\s*wholesale|bjswholesale",   "Groceries"),
    # Retail
    (r"kohl",                            "Shopping - Retail"),
    (r"marshalls",                       "Shopping - Retail"),
    # Health & Fitness
    (r"cvs",                             "Health & Fitness"),
    (r"walgreen",                        "Health & Fitness"),
    # Dining
    (r"mcdonald",                        "Dining"),
    (r"starbucks",                       "Dining"),
    (r"subway",                          "Dining"),
    (r"pizza",                           "Dining"),
    (r"restaurant",                      "Dining"),
    # Utilities
    (r"consumers\s*energy",              "Utilities"),
    (r"dte\s*energy",                    "Utilities"),
    (r"at&t",                            "Utilities"),
    (r"comcast",                         "Utilities"),
    (r"spectrum",                        "Utilities"),
]

COMPILED_RULES = [(re.compile(p, re.IGNORECASE), cat) for p, cat in CATEGORY_RULES]

# Friendly display names for known compact store codes
DISPLAY_NAMES = {
    "WMSUPERCENTER":   "Walmart Supercenter",
    "HOBBYLOBBY":      "Hobby Lobby",
    "BJSWHOLESALE":    "BJ's Wholesale",
    "HOLIDAYMARKETO5": "Holiday Market",
    "HOLIDAYMARKET":   "Holiday Market",
    "MEIJERSTORE":     "Meijer",
    "SAMSCLUB":        "Sam's Club",
    "MICHAELSSTORES":  "Michaels",
    "PLANETFITNESSC":  "Planet Fitness",
    "CIGNAPDP":        "Cigna",
    "FRESHTHYME":      "Fresh Thyme",
    "PEARTREE":        "Pear Tree",
    "BJSFUEL":         "BJ's Fuel",
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

# Regex patterns for different transaction types
DEBIT_CARD_RE = re.compile(
    r"^(\d{2}/\d{2})\s*PURCHASE\s*(.+?)\s*(\d{1,3}(?:,\d{3})*\.\d{2})\s*$"
)

# For Deposit/Credit and Other Withdrawal - simpler format
SIMPLE_TX_RE = re.compile(
    r"^(\d{2}/\d{2})\s+(.+?)\s+(\d{1,3}(?:,\d{3})*\.\d{2})\s*$"
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
    s = re.sub(r"[A-Z]{2,}(?:\s*[A-Z]{2,})*\s*FL\b.*$", "", s).strip()
    return friendly_name(s)


def clean_simple_description(raw: str) -> str:
    """Clean descriptions from Deposit/Credit and Other Withdrawal sections."""
    # These don't have the doubled format, just clean them up
    s = raw.strip()
    # Remove extra reference numbers and codes at the end
    s = re.sub(r"\s+[A-Z0-9]{10,}$", "", s)  # Remove long alphanumeric codes
    return s


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

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                all_text_lines.extend(text.splitlines())
    except Exception as e:
        print(f"  Error reading {pdf_path}: {e}")
        return []

    full_text = "\n".join(all_text_lines)
    statement_years = extract_statement_years(full_text)

    current_section = None

    for line in all_text_lines:
        stripped = line.strip()

        # Detect section headers
        if re.search(r"Deposit\s*/\s*Credit\s*Activity", stripped, re.IGNORECASE):
            current_section = "CREDIT"
            continue
        elif re.search(r"Debit\s*Card\s*/\s*POS\s*Activity", stripped, re.IGNORECASE):
            current_section = "DEBIT_CARD"
            continue
        elif re.search(r"Other\s*Withdrawal\s*/\s*Debit\s*Activity", stripped, re.IGNORECASE):
            current_section = "OTHER_DEBIT"
            continue
        
        # Exit current section when we hit certain headers
        if re.search(
            r"(Balance\s*Activity|Statement\s*Period|Page\s+\d+\s+of)",
            stripped, re.IGNORECASE
        ):
            current_section = None
            continue

        if not current_section:
            continue

        # Parse based on section type
        if current_section == "DEBIT_CARD":
            m = DEBIT_CARD_RE.match(stripped)
            if m:
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
                    "Amount":      -amount,  # Debit is negative
                    "Type":        "Debit Card"
                })

        elif current_section in ["CREDIT", "OTHER_DEBIT"]:
            m = SIMPLE_TX_RE.match(stripped)
            if m:
                date_raw   = m.group(1)
                desc_raw   = m.group(2)
                amount_raw = m.group(3)

                full_date   = infer_year(date_raw, statement_years)
                description = clean_simple_description(desc_raw)
                amount      = float(amount_raw.replace(",", ""))
                category    = categorize(description)

                tx_type = "Credit" if current_section == "CREDIT" else "Other Debit"
                signed_amount = amount if current_section == "CREDIT" else -amount

                transactions.append({
                    "Date":        full_date,
                    "Description": description,
                    "Category":    category,
                    "Amount":      signed_amount,
                    "Type":        tx_type
                })

    return transactions


def write_csv(transactions: list, output_path: str):
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["Date", "Description", "Category", "Amount", "Type"]
        )
        writer.writeheader()
        writer.writerows(transactions)
    print(f"\n✓ Wrote {len(transactions)} total transactions to {output_path}")


def main():
    # Default path - CHANGE THIS to your statements folder path
    DEFAULT_STATEMENTS_PATH = "statements"
    
    if len(sys.argv) < 2:
        # If no argument provided, use default path
        directory_path = Path(DEFAULT_STATEMENTS_PATH)
        csv_path = "combined_transactions.csv"
        print(f"No directory specified, using default: {directory_path}")
    else:
        directory_path = Path(sys.argv[1])
        csv_path = sys.argv[2] if len(sys.argv) >= 3 else "combined_transactions.csv"

    # Validate directory
    if not directory_path.exists():
        print(f"Error: Directory '{directory_path}' does not exist.")
        sys.exit(1)
    
    if not directory_path.is_dir():
        print(f"Error: '{directory_path}' is not a directory.")
        sys.exit(1)

    # Find all PDF files in the directory
    pdf_files = sorted(directory_path.glob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in '{directory_path}'")
        sys.exit(1)

    print(f"Found {len(pdf_files)} PDF file(s) in '{directory_path}'")
    print("-" * 60)

    # Process all PDFs and collect transactions
    all_transactions = []
    
    for pdf_file in pdf_files:
        print(f"Processing: {pdf_file.name}...", end=" ")
        transactions = parse_transactions(str(pdf_file))
        
        if transactions:
            print(f"✓ {len(transactions)} transactions")
            all_transactions.extend(transactions)
        else:
            print("⚠ No transactions found")

    if not all_transactions:
        print("\nNo transactions found in any PDF files.")
        sys.exit(1)

    # Sort all transactions by date ascending
    all_transactions.sort(key=lambda r: datetime.strptime(r["Date"], "%m/%d/%Y"))

    print("-" * 60)
    write_csv(all_transactions, csv_path)


if __name__ == "__main__":
    main()
