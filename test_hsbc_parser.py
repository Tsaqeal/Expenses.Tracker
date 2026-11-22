from datetime import datetime
import re
import pandas as pd
import pdfplumber

PDF_PATH = r"C:\Users\VTsak\Downloads\kS_2026-05-22_Statement.pdf"

DATE_RE = re.compile(r"^\d{2}\s+[A-Za-z]{3}\s+\d{2}$")
AMOUNT_RE = re.compile(r"^\d{1,3}(?:,\d{3})*\.\d{2}$")
PAYMENT_CODES = {
    ")))",
    "VIS",
    "CR",
    "DD",
    "OBP",
    "SO",
    "BP",
    "CHQ",
    "ATM",
    "FPO",
    "FPI",
}
SKIP_NORM = {
    "BALANCEBROUGHTFORWARD",
    "BALANCECARRIEDFORWARD",
    "ACCOUNTSUMMARY",
    "PAYMENTTYPEANDDETAILS",
    "PAIDOUT",
    "PAIDIN",
    "BALANCE",
    "DATE",
}


def normalize_token(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", text).upper()


def parse_hsbc_expenses(pdf_path: str) -> pd.DataFrame:
    extracted = []
    current_date = None

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(keep_blank_chars=False, y_tolerance=3)
            if not words:
                continue

            # Find column boundaries from "Paid out", "Paid in", "Balance" headers
            paid_out_x = None
            paid_in_x = None
            balance_x = None

            for i, w in enumerate(words):
                txt = w["text"].strip()
                if txt == "out" and i > 0 and words[i - 1]["text"] == "Paid":
                    paid_out_x = words[i - 1]["x0"] - 15
                elif txt == "in" and i > 0 and words[i - 1]["text"] == "Paid":
                    paid_in_x = words[i - 1]["x0"] - 15
                elif txt == "Balance" and w["x0"] > 350:
                    balance_x = w["x0"] - 15

            # Group words into visual rows
            rows_by_y = []
            for w in sorted(words, key=lambda x: (x["top"], x["x0"])):
                placed = False
                for row in rows_by_y:
                    if abs(row[0]["top"] - w["top"]) <= 4:
                        row.append(w)
                        placed = True
                        break
                if not placed:
                    rows_by_y.append([w])

            desc_buffer = []

            for row in rows_by_y:
                row_sorted = sorted(row, key=lambda x: x["x0"])
                line_norm = normalize_token(
                    "".join(w["text"] for w in row_sorted))

                # Ignore headers, summaries, and brought/carried forward lines
                if any(skip in line_norm for skip in SKIP_NORM):
                    desc_buffer = []
                    continue

                # Check for leading date (e.g. "24 Apr 26")
                first_three = " ".join(w["text"].strip()
                                       for w in row_sorted[:3])
                if DATE_RE.match(first_three):
                    current_date = datetime.strptime(first_three, "%d %b %y").strftime(
                        "%Y-%m-%d"
                    )
                    content_words = row_sorted[3:]
                else:
                    content_words = row_sorted

                if not current_date:
                    continue

                paid_out_val = None
                has_paid_in_or_balance = False
                line_desc_parts = []

                for w in content_words:
                    txt = w["text"].strip()
                    x0 = w["x0"]

                    if AMOUNT_RE.match(txt) and x0 > 250:
                        val = float(txt.replace(",", ""))
                        if paid_out_x is not None and paid_in_x is not None:
                            if paid_out_x <= x0 < paid_in_x:
                                paid_out_val = val
                            else:
                                has_paid_in_or_balance = True
                        else:
                            # Fallback x-ranges if header words weren't matched
                            if balance_x is not None and x0 >= balance_x:
                                has_paid_in_or_balance = True
                            elif x0 < 430:
                                paid_out_val = val
                            else:
                                has_paid_in_or_balance = True
                    else:
                        # Skip payment method codes and standalone £ symbols
                        if txt not in PAYMENT_CODES and txt != "£":
                            line_desc_parts.append(txt)

                if paid_out_val is not None:
                    if line_desc_parts:
                        desc_buffer.extend(line_desc_parts)
                    reason_clean = " ".join(desc_buffer).strip()
                    if reason_clean:
                        extracted.append({
                            "page": page_num,
                            "date": current_date,
                            "reason": reason_clean,
                            "amount": paid_out_val,
                        })
                    desc_buffer = []
                elif has_paid_in_or_balance:
                    # Row was a Paid In or Balance-only line; do not leak into next expense
                    desc_buffer = []
                else:
                    # Continuation or merchant header line
                    if line_desc_parts:
                        desc_buffer.extend(line_desc_parts)

    return pd.DataFrame(extracted)


if __name__ == "__main__":
    df = parse_hsbc_expenses(PDF_PATH)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 1000)
    print(df.to_string(index=False))
    if not df.empty:
        print(
            f"\nRows: {len(df)} | Total Paid Out: £{df['amount'].sum():,.2f}"
        )
