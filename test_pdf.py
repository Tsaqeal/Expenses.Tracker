import os
import re
import pdfplumber

pdf_path = os.path.expanduser(
    r"~\Downloads\VT_2026_May_Statement.pdf"
)

print(f"--- Universal Parser Test: {pdf_path} ---\n")

with pdfplumber.open(pdf_path) as pdf:
    for page_num, page in enumerate(pdf.pages, start=1):
        text = page.extract_text()
        if text:
            for line in text.split("\n"):
                line_clean = line.strip()

                if "Money Out (£)" in line_clean and "Column" not in line_clean:

                    # Date Parser
                    date_match = re.search(
                        r"D(\d)ate\s*(\d)?\s*([A-Za-z]{3}\s+\d{2})", line_clean)
                    if date_match:
                        tens, units, month_yr = date_match.groups()
                        tx_date = f"{tens}{units or ''} {month_yr}"
                    else:
                        tx_date = "Unknown Date"

                    # Universal Description Cleaner
                    desc_prefix_match = re.search(
                        r"D([A-Za-z])escription", line_clean)
                    prefix_letter = desc_prefix_match.group(
                        1) if desc_prefix_match else ""

                    clean_desc = re.sub(r"^.*?escription\s*", "", line_clean)
                    clean_desc = re.sub(r"T(?:D|P|F)ype.*", "", clean_desc)
                    clean_desc = re.sub(r"Moneyb.*", "", clean_desc)
                    clean_desc = re.sub(
                        r"[0-9,]+\.\d{2}Money Out.*", "", clean_desc).strip()

                    if prefix_letter and not clean_desc.upper().startswith(prefix_letter.upper()):
                        clean_desc = prefix_letter + clean_desc

                    # Amount Parser
                    amt_match = re.search(
                        r"([0-9,]+\.\d{2})Money Out \(£\)", line_clean)
                    tx_amount = amt_match.group(1) if amt_match else "0.00"

                    print(
                        f"Date: {tx_date} | Reason: {clean_desc} | Amount: £{tx_amount}")

print("\n--- Test Complete ---")
