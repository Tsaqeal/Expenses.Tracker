import os
import re
import pdfplumber

pdf_path = os.path.expanduser(
    r"~\Downloads\VT_2026_October_Statement.pdf"
)

print(f"--- Parsing Clean Expenses from: {pdf_path} ---\n")

with pdfplumber.open(pdf_path) as pdf:
    for page_num, page in enumerate(pdf.pages, start=1):
        text = page.extract_text()
        if text:
            for line in text.split("\n"):
                line_clean = line.strip()

                # Only process 'Money Out' transaction lines (skip headers and Money In)
                if "Money Out (£)" in line_clean and "Column" not in line_clean:

                    # 1. Fix Date: reconstruct from D[tens]ate [units] [Month Year]
                    date_match = re.search(
                        r"D(\d)ate\s+(\d)\s+([A-Za-z]{3}\s+\d{2})", line_clean)
                    if date_match:
                        tens, units, month_yr = date_match.groups()
                        tx_date = f"{tens}{units} {month_yr}"
                    else:
                        tx_date = "Unknown Date"

                    # 2. Fix Description: combine the prefix letter with the rest of the text
                    desc_match = re.search(
                        r"D([A-Za-z])escription\s+(.*?)TDype", line_clean)
                    if desc_match:
                        first_letter, rest_desc = desc_match.groups()
                        # If the rest doesn't already start with that letter, prepend it
                        if not rest_desc.upper().startswith(first_letter.upper()):
                            tx_desc = first_letter + rest_desc
                        else:
                            tx_desc = rest_desc
                    else:
                        tx_desc = "Unknown Description"

                    # 3. Extract Amount: capture the monetary value right before "Money Out (£)"
                    amt_match = re.search(
                        r"([0-9,]+\.\d{2})Money Out \(£\)", line_clean)
                    if amt_match:
                        tx_amount = amt_match.group(1)
                    else:
                        tx_amount = "0.00"

                    print(
                        f"Date: {tx_date} | Reason: {tx_desc.strip()} | Amount: £{tx_amount}")

print("\n--- Test Complete ---")
