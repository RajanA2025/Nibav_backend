import streamlit as st
import os
from PyPDF2 import PdfReader

st.set_page_config(page_title="📄 PDF Word-Comma Extractor", page_icon="📄")
st.title("📄 Extract and Comma-Separate Text from PDF")

# Folder where PDF files are stored
data_dir = "data"
pdf_files = [f for f in os.listdir(data_dir) if f.lower().endswith(".pdf")]

if not pdf_files:
    st.warning("No PDF files found in the 'data' folder.")
    st.stop()

# Dropdown to select a PDF file
pdf_filename = st.selectbox("Choose a PDF file to extract text from:", pdf_files)
pdf_path = os.path.join(data_dir, pdf_filename)

# Extract button
if st.button("🪄 Extract Text"):
    with st.spinner("Reading PDF content..."):
        try:
            reader = PdfReader(pdf_path)
            full_text = ""

            for page_num, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    full_text += f"\n\n--- Page {page_num + 1} ---\n{text.strip()}"

            if not full_text.strip():
                st.error("❌ No readable text found in the PDF.")
                st.stop()

            st.success("✅ Text extracted successfully.")
            # 📌 Convert entire text into a single paragraph with comma-separated words
            all_words = []
            for line in full_text.splitlines():
                words = [w.strip(".,!?;:-–—()[]\"'") for w in line.split()]
                all_words.extend([w for w in words if w])  # remove empty strings

            formatted_text = ", ".join(all_words)


            # Show comma-separated output
            st.text_area("📄 Extracted Text (Comma-Separated Words):", formatted_text, height=600)

            # Save and offer download
            output_path = os.path.join(data_dir, "comma_text.txt")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(formatted_text)

            with open(output_path, "rb") as f:
                st.download_button("📥 Download Comma-Separated Text", f, file_name="comma_text.txt", mime="text/plain")

        except Exception as e:
            st.error(f"❌ Failed to read PDF: {e}")
