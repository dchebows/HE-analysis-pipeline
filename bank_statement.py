Microsoft Azure
Search data, notebooks, recents, and more...
CTRL + P
Playground
Try the Supervisor API
Build production-ready agents that orchestrate tools, models, and data with a single API call.
I have a script that I need to read in several bank statements and create one large CSV file with all the data.  Can you modify this script to do that.  Ask questions as needed.  """
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
I'd be happy to help modify this script to handle multiple bank statements! Before I make the changes, I have a few questions:
How do you want to specify the input PDFs?
Pass multiple PDF files as command-line arguments? (e.g., python parse_huntington.py stmt1.pdf stmt2.pdf stmt3.pdf output.csv)
Point to a directory and process all PDFs in it? (e.g., python parse_huntington.py ./statements/ output.csv)
Both options?
Should the script handle duplicate transactions? If the same transaction appears in multiple statements (e.g., overlapping statement periods), should it:
Keep all duplicates
Remove duplicates automatically
Add a column to show which statement file each transaction came from
Sorting preference? Should the final CSV be:
Sorted by date (ascending/descending)
Grouped by source file, then sorted
Keep the current date sorting
Are all the PDFs Huntington bank statements with the same format, or might you have statements from different banks in the future?
Output filename: Should the output CSV name be:
Required command-line argument
Optional with a default name like "combined_transactions.csv"
Let me know your preferences and I'll modify the script accordingly!
1.  point to a directory. 2. keep all duplicates.  3. Sort by assending date.  4. Yes.  5. "combined_transactions.csv" is good
Perfect! Here's the modified script that processes all PDFs in a directory and combines them into one CSV:
ExamplePython
"""
parse_huntington.py
--------------------
Extracts the "Debit Card / POS Activity (-)" section from Huntington Bank
PDF statements in a directory, auto-categorizes each transaction, and writes 
a combined CSV with columns: Date, Description, Category, Amount.

Usage:
    python parse_huntington.py <directory_path> [output_csv]

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

    return transactions


def write_csv(transactions: list, output_path: str):
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["Date", "Description", "Category", "Amount"]
        )
        writer.writeheader()
        writer.writerows(transactions)
    print(f"\n✓ Wrote {len(transactions)} total transactions to {output_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python parse_huntington.py <directory_path> [output.csv]")
        sys.exit(1)

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
        print("\nNo debit card transactions found in any PDF files.")
        sys.exit(1)

    # Sort all transactions by date ascending
    all_transactions.sort(key=lambda r: datetime.strptime(r["Date"], "%m/%d/%Y"))

    print("-" * 60)
    write_csv(all_transactions, csv_path)


if __name__ == "__main__":
    main()
Key Changes:
Directory Processing: Now accepts a directory path and processes all .pdf files in it
Multiple PDFs: Loops through all found PDFs and collects transactions from each
Progress Output: Shows which file is being processed and how many transactions were found in each
Error Handling: Added try/except when opening PDFs so one bad file doesn't stop the whole process
Default Output: Uses "combined_transactions.csv" as default output filename
Validation: Checks that the provided path is actually a directory
Usage:
Example
# Process all PDFs in a directory (output to combined_transactions.csv)
python parse_huntington.py ./statements/

# Process all PDFs in a directory with custom output name
python parse_huntington.py ./statements/ my_transactions.csv
The script will show progress like:
Example
Found 3 PDF file(s) in './statements'
------------------------------------------------------------
Processing: statement_2024_01.pdf... ✓ 45 transactions
Processing: statement_2024_02.pdf... ✓ 52 transactions
Processing: statement_2024_03.pdf... ✓ 48 transactions
------------------------------------------------------------

✓ Wrote 145 total transactions to combined_transactions.csv
How do I point this to the pdf files?  where do I find the output?
Great questions! Let me clarify with some examples:
How to Point to PDF Files:
You need to tell the script where your PDF files are located. Here are common scenarios:
Scenario 1: PDFs are in a subfolder
If your PDFs are in a folder called statements in the same location as your script:
Example
python parse_huntington.py statements
Or with full path:
Example
python parse_huntington.py C:/Users/YourName/Documents/statements
Scenario 2: PDFs are in the same folder as the script
If your PDFs are right next to the script file:
Example
python parse_huntington.py .
(The . means "current directory")
Scenario 3: PDFs are somewhere else
Example
python parse_huntington.py C:/Users/YourName/Downloads/bank_statements
Where to Find the Output:
By default, the output CSV will be created in whatever folder you run the command from (your current working directory).
Example:
If you're in C:/Users/YourName/Documents and run:
Example
python parse_huntington.py statements
The output will be: C:/Users/YourName/Documents/combined_transactions.csv
To specify exactly where you want the output:
Example
python parse_huntington.py statements C:/Users/YourName/Desktop/my_output.csv
Quick Setup Guide:
Put your PDF files in a folder (let's say bank_pdfs)
Open a terminal/command prompt
Navigate to where your script is:
Example
cd C:/path/to/your/script
Run the command:
Example
python parse_huntington.py bank_pdfs
Look for combined_transactions.csv in the same folder as your script
Would you like me to adjust the script to save the output in a specific location by default, or is this clear now?
the script and the data are in C:\Users\dcheb\Documnets\Python Projects\hunniington_statement_parse.  Where do I stick this?
Perfect! Here's exactly what to do:
File Organization:
In your folder C:\Users\dcheb\Documents\Python Projects\huntington_statement_parse:
Example
huntington_statement_parse/
├── parse_huntington.py          ← Your script
├── statements/                   ← Create this folder for your PDFs
│   ├── statement1.pdf
│   ├── statement2.pdf
│   └── statement3.pdf
└── combined_transactions.csv    ← Output will appear here after running
Steps:
Create a subfolder called statements inside your project folder
Put all your PDF files in that statements folder
Open Command Prompt in your project folder:
Open File Explorer and navigate to C:\Users\dcheb\Documents\Python Projects\huntington_statement_parse
Click in the address bar at the top and type cmd then press Enter
This opens a command prompt already in the right folder
Run this command:
Example
python parse_huntington.py statements
The output file combined_transactions.csv will appear in the same folder as your script
Alternative (if PDFs are already in the main folder):
If your PDFs are directly in huntington_statement_parse folder (not in a subfolder):
Example
python parse_huntington.py .
The . means "look in the current directory"
To check it worked:
After running, you should see something like:
Example
Found 3 PDF file(s) in 'statements'
------------------------------------------------------------
Processing: statement_2024_01.pdf... ✓ 45 transactions
...
✓ Wrote 145 total transactions to combined_transactions.csv
Does this make sense? Where are your PDF files currently located?
ok.  I created the statements folder and put the pdfs in it.  Ran the script, still no csv output, no warings or errors in the teminal window.
Hmm, no output at all is unusual. Let's debug this step by step.
Can you tell me exactly what you see in the terminal window? Even if it's blank, that's helpful to know.
Let me give you a debug version of the script that will print more information. Replace your current script with this version:
ExamplePython
"""
parse_huntington.py - DEBUG VERSION
"""

import re
import sys
import csv
from datetime import datetime
from pathlib import Path

import pdfplumber

# (Keep all your CATEGORY_RULES, COMPILED_RULES, DISPLAY_NAMES, etc. the same)
# ... [all the same code as before] ...

def main():
    print("=== SCRIPT STARTED ===")
    print(f"Arguments received: {sys.argv}")
    print(f"Number of arguments: {len(sys.argv)}")
    
    if len(sys.argv) < 2:
        print("Usage: python parse_huntington.py <directory_path> [output.csv]")
        sys.exit(1)

    directory_path = Path(sys.argv[1])
    csv_path = sys.argv[2] if len(sys.argv) >= 3 else "combined_transactions.csv"

    print(f"Directory path: {directory_path}")
    print(f"Absolute path: {directory_path.absolute()}")
    print(f"Output CSV: {csv_path}")

    # Validate directory
    if not directory_path.exists():
        print(f"Error: Directory '{directory_path}' does not exist.")
        sys.exit(1)
    
    if not directory_path.is_dir():
        print(f"Error: '{directory_path}' is not a directory.")
        sys.exit(1)

    print("Directory validated successfully!")

    # Find all PDF files in the directory
    pdf_files = sorted(directory_path.glob("*.pdf"))
    
    print(f"PDF files found: {len(pdf_files)}")
    for pdf in pdf_files:
        print(f"  - {pdf.name}")
    
    if not pdf_files:
        print(f"No PDF files found in '{directory_path}'")
        sys.exit(1)

    print(f"Found {len(pdf_files)} PDF file(s) in '{directory_path}'")
    print("-" * 60)

    # (rest of your main() function stays the same)
    # ...

if __name__ == "__main__":
    main()
Or, try this simpler test first:
Just run this command to see if Python is working:
Example
python parse_huntington.py
You should see: Usage: python parse_huntington.py <directory_path> [output.csv]
If you see nothing at all, the issue might be:
Python isn't in your PATH
The script file name is wrong
You need to use python3 instead of python
What do you see when you type:
Example
python --version
This is what I see in the termainal window. (.venv) PS C:\Users\dcheb\Documents\Python Projects\hunnington_statement_parse> & "c:\Users\dcheb\Documents\Python Projects\hunnington_statement_parse\.venv\Scripts\python.exe" "c:/Users/dcheb/Documents/Python Projects/hunnington_statement_parse/bank_statement.py"
Usage: python parse_huntington.py <directory_path> [output.csv]
(.venv) PS C:\Users\dcheb\Documents\Python Projects\hunnington_statement_parse> 
Aha! I see the issue!
Your script is named bank_statement.py but you're running it without the directory argument.
Notice the script says:
Example
Usage: python parse_huntington.py <directory_path> [output.csv]
You need to tell it to look in the statements folder!
Solution:
In your PowerShell terminal, type:
Example
python bank_statement.py statements
Or with the full path:
Example
& "c:\Users\dcheb\Documents\Python Projects\hunnington_statement_parse\.venv\Scripts\python.exe" "c:/Users/dcheb/Documents/Python Projects/hunnington_statement_parse/bank_statement.py" statements
Even Easier - Just type this in your terminal:
Example
python bank_statement.py statements
Since you're already in the right directory, this should work perfectly!
Why this happened: It looks like you're clicking the "Run" button in VS Code (or similar), which runs the script but doesn't pass the directory argument. You need to run it from the terminal with the statements argument so it knows where to look for your PDFs.
Try it now and let me know what you see! 🎯
ok.  it did run.  I took a look at the results.  It seems to be missing some of the transactions under Other Withdrawal / Debit Activity (-), Deposit / Credit Activity (+) and maybe some other activty table.  I dont care about the Asterisk-Free Checking Balance Activity Account: table.  Can you modify the script to include these sections?  Also, is there a way we can write the path into the VS code so it can be run with the run button?
Documents
Perfect! I can see the statement now. You're right - the script is currently only capturing "Debit Card / POS Activity (-)" but missing:
Deposit / Credit Activity (+) - deposits, returns, SSA payments
Other Withdrawal / Debit Activity (-) - Planet Fitness, UnitedHealthcare, etc.
Let me modify the script to capture all these sections!
Updated Script:
ExamplePython
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
            f, fieldfields=["Date", "Description", "Category", "Amount", "Type"]
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
To Use the Run Button in VS Code:
Option 1: Quick Fix - I added a default path at the top of the script. Now you can just click Run and it will use the statements folder by default!
Option 2: Configure VS Code Launch Settings:
In VS Code, press Ctrl+Shift+D (or click the Run icon)
Click "create a launch.json file"
Add this configuration:
ExampleJSON
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Parse Bank Statements",
            "type": "python",
            "request": "launch",
            "program": "${file}",
            "args": ["statements", "combined_transactions.csv"],
            "console": "integratedTerminal"
        }
    ]
}
Now when you press F5, it will run with the arguments!
Key Changes:
✅ Now captures Deposit/Credit Activity (deposits, returns, SSA payments)
✅ Now captures Other Withdrawal/Debit Activity (subscriptions, insurance)
✅ Ignores Balance Activity (not transaction data)
✅ Added "Type" column to show Credit vs Debit vs Other
✅ Amounts are signed (+ for credits, - for debits)
✅ Can run with Run button using default path
Try it out and let me know if it catches all the transactions now! 🎯
2s to first token + 66s
•
67 tokens/sec
•
4590 tokens
•
Start typing ...
Models called in Playground may be subject to license requirements and/or use policies. Learn more
