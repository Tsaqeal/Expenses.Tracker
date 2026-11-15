import os
import pdfplumber

# Direct path to your Downloads folder
pdf_path = os.path.expanduser(
    r"~\Downloads\VT_2026_October_Statement.pdf"
)

print(f"--- Opening: {pdf_path} ---\n")

with pdfplumber.open(pdf_path) as pdf:
    for page_num, page in enumerate(pdf.pages, start=1):
        print(f"=== Page {page_num} ===")
        tables = page.extract_tables()

        if not tables:
            print("No tables found on this page.")
            continue

        for table_idx, table in enumerate(tables):
            print(f"--- Table {table_idx + 1} ---")
            for row_idx, row in enumerate(table):
                print(f"Row {row_idx}: {row}")

        print("\n" + "=" * 40 + "\n")

print("--- Test Complete ---")
