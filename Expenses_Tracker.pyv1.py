import streamlit as st
import pandas as pd
import pdfplumber
import re
from supabase import create_client, Client

# --- Supabase Configuration ---
SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["key"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Expenses Tracker", page_icon="💰", layout="wide")

st.title("💰 Personal Expenses Tracker")

# --- Navigation Tabs ---
tab1, tab2 = st.tabs(["➕ Add Single Expense", "📥 Bulk Import Lloyds PDF"])

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
                    "amount": amount
                }).execute()
                st.success("Expense saved successfully to Supabase!")
            except Exception as e:
                st.error(f"Error saving expense: {e}")

# --- TAB 2: Bulk PDF Statement Import ---
with tab2:
    st.header("Bulk Import Lloyds Bank Statement (PDF)")
    st.markdown(
        "Upload your monthly Lloyds statement PDF to automatically filter and import all **Money Out** expenses.")

    uploaded_pdf = st.file_uploader(
        "Upload Monthly Statement PDF", type=["pdf"])

    if uploaded_pdf is not None:
        extracted_expenses = []

        with pdfplumber.open(uploaded_pdf) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    for line in text.split("\n"):
                        line_clean = line.strip()

                        # Filter strictly for 'Money Out' transaction lines
                        if "Money Out (£)" in line_clean and "Column" not in line_clean:

                            # 1. Robust Date Parser
                            date_match = re.search(
                                r"D(\d)ate\s*(\d)?\s*([A-Za-z]{3}\s+\d{2})", line_clean)
                            if date_match:
                                tens, units, month_yr = date_match.groups()
                                tx_date = f"{tens}{units or ''} {month_yr}"
                            else:
                                tx_date = "Unknown Date"

                            # 2. Universal Description Cleaner & Prefix Rescuer
                            desc_prefix_match = re.search(
                                r"D([A-Za-z])escription", line_clean)
                            prefix_letter = desc_prefix_match.group(
                                1) if desc_prefix_match else ""

                            clean_desc = re.sub(
                                r"^.*?escription\s*", "", line_clean)
                            clean_desc = re.sub(
                                r"T(?:D|P|F)ype.*", "", clean_desc)
                            clean_desc = re.sub(r"Moneyb.*", "", clean_desc)
                            clean_desc = re.sub(
                                r"[0-9,]+\.\d{2}Money Out.*", "", clean_desc).strip()

                            if prefix_letter and not clean_desc.upper().startswith(prefix_letter.upper()):
                                clean_desc = prefix_letter + clean_desc

                            # 3. Amount Parser
                            amt_match = re.search(
                                r"([0-9,]+\.\d{2})Money Out \(£\)", line_clean)
                            if amt_match:
                                try:
                                    tx_amount = float(
                                        amt_match.group(1).replace(",", ""))
                                    extracted_expenses.append({
                                        "date": tx_date,
                                        "reason": clean_desc,
                                        "amount": tx_amount
                                    })
                                except ValueError:
                                    pass

        if extracted_expenses:
            df_expenses = pd.DataFrame(extracted_expenses)
            st.success(
                f"Successfully extracted {len(df_expenses)} outgoing expenses!")

            st.markdown("### Review & Edit Extracted Expenses Before Saving:")
            edited_df = st.data_editor(
                df_expenses, num_rows="dynamic", use_container_width=True)

            if st.button("🚀 Save All to Supabase Database"):
                success_count = 0
                for _, row in edited_df.iterrows():
                    try:
                        supabase.table("expenses").insert({
                            "date": str(row["date"]),
                            "reason": str(row["reason"]),
                            "amount": float(row["amount"])
                        }).execute()
                        success_count += 1
                    except Exception as e:
                        st.error(f"Error saving row: {e}")

                st.success(
                    f"Successfully saved {success_count} expenses to Supabase!")
        else:
            st.warning("No outgoing transactions found in this PDF.")
