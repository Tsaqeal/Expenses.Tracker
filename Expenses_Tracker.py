from datetime import datetime
import re
import pandas as pd
import pdfplumber
import streamlit as st
from supabase import Client, create_client

# --- Supabase Configuration ---
SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["key"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Expenses Tracker", page_icon="💰", layout="wide")
st.title("💰 Personal Expenses Tracker")

# --- HSBC Parser Constants ---
HSBC_DATE_RE = re.compile(r"^\d{2}\s+[A-Za-z]{3}\s+\d{2}$")
HSBC_AMOUNT_RE = re.compile(r"^\d{1,3}(?:,\d{3})*\.\d{2}$")
HSBC_PAYMENT_CODES = {
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
HSBC_SKIP_NORM = {
    "BALANCEBROUGHTFORWARD",
    "BALANCECARRIEDFORWARD",
    "ACCOUNTSUMMARY",
    "PAYMENTTYPEANDDETAILS",
    "PAIDOUT",
    "PAIDIN",
    "BALANCE",
    "DATE",
}


def _normalize_hsbc_token(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", text).upper()


def parse_hsbc_pdf(pdf_file) -> list[dict]:
    extracted = []
    current_date = None

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            words = page.extract_words(keep_blank_chars=False, y_tolerance=3)
            if not words:
                continue

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
                line_norm = _normalize_hsbc_token(
                    "".join(w["text"] for w in row_sorted)
                )

                if any(skip in line_norm for skip in HSBC_SKIP_NORM):
                    desc_buffer = []
                    continue

                first_three = " ".join(w["text"].strip()
                                       for w in row_sorted[:3])
                if HSBC_DATE_RE.match(first_three):
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

                    if HSBC_AMOUNT_RE.match(txt) and x0 > 250:
                        val = float(txt.replace(",", ""))
                        if paid_out_x is not None and paid_in_x is not None:
                            if paid_out_x <= x0 < paid_in_x:
                                paid_out_val = val
                            else:
                                has_paid_in_or_balance = True
                        else:
                            if balance_x is not None and x0 >= balance_x:
                                has_paid_in_or_balance = True
                            elif x0 < 430:
                                paid_out_val = val
                            else:
                                has_paid_in_or_balance = True
                    else:
                        if txt not in HSBC_PAYMENT_CODES and txt != "£":
                            line_desc_parts.append(txt)

                if paid_out_val is not None:
                    if line_desc_parts:
                        desc_buffer.extend(line_desc_parts)
                    reason_clean = " ".join(desc_buffer).strip()
                    if reason_clean:
                        extracted.append({
                            "date": current_date,
                            "reason": reason_clean,
                            "amount": paid_out_val,
                        })
                    desc_buffer = []
                elif has_paid_in_or_balance:
                    desc_buffer = []
                else:
                    if line_desc_parts:
                        desc_buffer.extend(line_desc_parts)

    return extracted


# --- Navigation Tabs ---
tab1, tab2, tab3 = st.tabs([
    "➕ Add Single Expense",
    "📥 Bulk Import Lloyds PDF",
    "📥 Bulk Import HSBC PDF",
])

# --- TAB 1: Single Expense Entry ---
with tab1:
    st.header("Add a Single Expense")
    with st.form("single_expense_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("Date")
            reason = st.text_input("Reason / Merchant")
        with col2:
            amount = st.number_input(
                "Amount (£)", min_value=0.0, format="%.2f")

        submitted = st.form_submit_button("Save Expense")
        if submitted:
            try:
                supabase.table("expenses").insert({
                    "date": str(date),
                    "reason": reason,
                    "amount": amount,
                }).execute()
                st.success("Expense saved successfully to Supabase!")
            except Exception as e:
                st.error(f"Error saving expense: {e}")

# --- TAB 2: Bulk PDF Statement Import (Lloyds) ---
with tab2:
    st.header("Bulk Import Lloyds Bank Statement (PDF)")
    st.markdown(
        "Upload your monthly Lloyds statement PDF to automatically filter and"
        " import all **Money Out** expenses."
    )

    uploaded_lloyds_pdf = st.file_uploader(
        "Upload Lloyds Statement PDF", type=["pdf"], key="lloyds_uploader"
    )

    if uploaded_lloyds_pdf is not None:
        extracted_expenses = []

        with pdfplumber.open(uploaded_lloyds_pdf) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    for line in text.split("\n"):
                        line_clean = line.strip()

                        # Filter strictly for 'Money Out' transaction lines
                        if "Money Out (£)" in line_clean and "Column" not in line_clean:

                            # 1. Robust Date Parser
                            date_match = re.search(
                                r"D(\d)ate\s*(\d)?\s*([A-Za-z]{3}\s+\d{2})", line_clean
                            )
                            if date_match:
                                tens, units, month_yr = date_match.groups()
                                tx_date = f"{tens}{units or ''} {month_yr}"
                            else:
                                tx_date = "Unknown Date"

                            # 2. Universal Description Cleaner & Prefix Rescuer
                            desc_prefix_match = re.search(
                                r"D([A-Za-z])escription", line_clean
                            )
                            prefix_letter = (
                                desc_prefix_match.group(
                                    1) if desc_prefix_match else ""
                            )

                            clean_desc = re.sub(
                                r"^.*?escription\s*", "", line_clean)
                            clean_desc = re.sub(
                                r"T(?:D|P|F)ype.*", "", clean_desc)
                            clean_desc = re.sub(r"Moneyb.*", "", clean_desc)
                            clean_desc = re.sub(
                                r"[0-9,]+\.\d{2}Money Out.*", "", clean_desc
                            ).strip()

                            if prefix_letter and not clean_desc.upper().startswith(
                                prefix_letter.upper()
                            ):
                                clean_desc = prefix_letter + clean_desc

                            # 3. Amount Parser
                            amt_match = re.search(
                                r"([0-9,]+\.\d{2})Money Out \(£\)", line_clean
                            )
                            if amt_match:
                                try:
                                    tx_amount = float(
                                        amt_match.group(1).replace(",", ""))
                                    extracted_expenses.append({
                                        "date": tx_date,
                                        "reason": clean_desc,
                                        "amount": tx_amount,
                                    })
                                except ValueError:
                                    pass

        if extracted_expenses:
            df_expenses = pd.DataFrame(extracted_expenses)
            st.success(
                f"Successfully extracted {len(df_expenses)} outgoing expenses!"
            )

            st.markdown("### Review & Edit Extracted Expenses Before Saving:")
            edited_df = st.data_editor(
                df_expenses,
                num_rows="dynamic",
                use_container_width=True,
                key="lloyds_editor",
            )

            if st.button("🚀 Save All to Supabase Database", key="save_lloyds"):
                success_count = 0
                for _, row in edited_df.iterrows():
                    try:
                        supabase.table("expenses").insert({
                            "date": str(row["date"]),
                            "reason": str(row["reason"]),
                            "amount": float(row["amount"]),
                        }).execute()
                        success_count += 1
                    except Exception as e:
                        st.error(f"Error saving row: {e}")

                st.success(
                    f"Successfully saved {success_count} expenses to Supabase!")
        else:
            st.warning("No outgoing transactions found in this PDF.")

# --- TAB 3: Bulk PDF Statement Import (HSBC) ---
with tab3:
    st.header("Bulk Import HSBC Bank Statement (PDF)")
    st.markdown(
        "Upload your monthly HSBC statement PDF to automatically extract all"
        " **£ Paid out** expenses."
    )

    uploaded_hsbc_pdf = st.file_uploader(
        "Upload HSBC Statement PDF", type=["pdf"], key="hsbc_uploader"
    )

    if uploaded_hsbc_pdf is not None:
        hsbc_expenses = parse_hsbc_pdf(uploaded_hsbc_pdf)

        if hsbc_expenses:
            df_hsbc = pd.DataFrame(hsbc_expenses)
            total_out = df_hsbc["amount"].sum()
            st.success(
                f"Successfully extracted {len(df_hsbc)} outgoing expenses"
                f" (Total: £{total_out:,.2f})!"
            )

            st.markdown("### Review & Edit Extracted Expenses Before Saving:")
            edited_hsbc_df = st.data_editor(
                df_hsbc,
                num_rows="dynamic",
                use_container_width=True,
                key="hsbc_editor",
            )

            if st.button("🚀 Save All to Supabase Database", key="save_hsbc"):
                success_count = 0
                for _, row in edited_hsbc_df.iterrows():
                    try:
                        supabase.table("expenses").insert({
                            "date": str(row["date"]),
                            "reason": str(row["reason"]),
                            "amount": float(row["amount"]),
                        }).execute()
                        success_count += 1
                    except Exception as e:
                        st.error(f"Error saving row: {e}")

                st.success(
                    f"Successfully saved {success_count} expenses to Supabase!")
        else:
            st.warning("No outgoing transactions found in this HSBC PDF.")
