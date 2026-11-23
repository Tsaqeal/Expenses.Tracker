# 💰 Personal Expenses Tracker

A lightweight Python & Streamlit web app for logging single expenses and bulk-importing monthly bank statements (Lloyds & HSBC PDFs) directly into a Supabase PostgreSQL database.

## ✨ Features

* **Single Expense Entry:** Quick manual form to log individual expenses (`date`, `reason`, `amount`).

* **Lloyds PDF Bulk Import:** Extracts outgoing `Money Out (£)` transactions from Lloyds Bank PDF statements.

* **HSBC PDF Bulk Import:** Parses HSBC UK PDF statements using word-coordinate layout detection to handle carried-forward dates, multi-line merchant descriptions, and `£ Paid out` amounts while ignoring incoming payments and balances.

* **Interactive Preview & Edit:** Review, clean up merchant names, or remove rows in an editable table (`st.data_editor`) before saving to Supabase.

## 🛠️ Tech Stack

* **Frontend / UI:** [Streamlit](https://streamlit.io/)

* **PDF Parsing:** [pdfplumber](https://github.com/jsvine/pdfplumber) & [pandas](https://pandas.pydata.org/)

* **Database:** [Supabase](https://supabase.com/) (`public.expenses`)

## 🗄️ Database Schema

Create a table named `expenses` in your Supabase `public` schema with the following columns:

| Column | Type | Description | 
| ----- | ----- | ----- | 
| `id` | `int8` | Primary key (auto-generated) | 
| `created_at` | `timestamptz` | Timestamp (default `now()`) | 
| `date` | `date` | Transaction date (`YYYY-MM-DD`) | 
| `amount` | `float8` | Expense amount in GBP (`£`) | 
| `reason` | `text` | Merchant or expense description | 

## 🚀 Local Setup & Usage

1. **Clone the repository:**

   ```
   git clone https://github.com/Tsaqeal/Expenses.Tracker.git
   cd Expenses.Tracker
   
   ```

2. **Install dependencies:**

   ```
   pip install -r requirements.txt
   
   ```

3. **Configure Supabase credentials locally:**
   Create a `.streamlit/secrets.toml` file in the project root (this file is ignored by Git so your keys stay private):

   ```
   [supabase]
   url = "https://your-project-id.supabase.co"
   key = "your-supabase-anon-or-service-key"
   
   ```

4. **Run the Streamlit app:**

   ```
   streamlit run Expenses_Tracker.py
   
   ```

## 🔒 Privacy & Security Notes

* Never commit `.streamlit/secrets.toml`, `.env` files, or personal bank statement `.pdf` files to GitHub.

* When running the standalone parser test script locally, pass your PDF path via the command line rather than hardcoding local paths:

  ```
  python test_hsbc_parser.py "path/to/statement.pdf"
  
  ```
