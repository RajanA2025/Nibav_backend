import camelot
import pandas as pd
import os

def extract_faq_from_pdf(pdf_path, output_csv="output.csv"):
    # Read all tables from the PDF
    tables = camelot.read_pdf(pdf_path, pages='all', flavor='stream')

    if tables.n == 0:
        print("No tables found.")
        return None

    faq_entries = []

    for table in tables:
        df = table.df

        # Try to find the correct columns by matching headers
        for i in range(len(df)):
            header_row = df.iloc[i]
            if "Question" in header_row.to_string() and "Concise Answer" in header_row.to_string():
                df.columns = df.iloc[i]
                df = df[i+1:]
                break

        # Clean column names
        df.columns = [col.strip() for col in df.columns]

        # Rename columns if necessary
        df = df.rename(columns={
            "Question": "Question",
            "Concise Answer (bot default)": "Concise Answer (bot default)",
            "Details if user asks \"Tell me more\"": "Details if user asks \"Tell me more\""
        })

        for idx, row in df.iterrows():
            question = str(row.get("Question", "")).strip()
            short_ans = str(row.get("Concise Answer (bot default)", "")).strip()
            long_ans = str(row.get("Details if user asks \"Tell me more\"", "")).strip()

            if question and short_ans:
                faq_entries.append({
                    "Question": question,
                    "Concise Answer (bot default)": short_ans,
                    "Details if user asks \"Tell me more\"": long_ans
                })

    if not faq_entries:
        print("No FAQ entries extracted.")
        return None

    output_df = pd.DataFrame(faq_entries)
    output_df.to_csv(output_csv, index=False)
    print(f"✅ Extracted {len(output_df)} entries. Saved to: {output_csv}")

    return output_df


# Example usage
pdf_file_path = "C:\\Nibav_FAQ"  # ← Replace with your PDF filename
extract_faq_from_pdf(pdf_file_path, output_csv="nibav_faq.csv")
