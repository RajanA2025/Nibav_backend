#!/usr/bin/env python3
"""
Process both CSV and PDF files and store in FAISS using AWS Bedrock
"""

import logging
import os
from bedrock_faiss_indexer import BedrockFAISSIndexer

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def process_documents_to_faiss(index_path: str = "bedrock_faiss_index"):
    """
    Process all CSV and PDF files in the data folder and store in FAISS using AWS Bedrock
    """
    print("🚀 Starting document processing with AWS Bedrock...")
    data_dir = "data"
    try:
        # Initialize Bedrock FAISS indexer
        print("📡 Initializing AWS Bedrock FAISS indexer...")
        indexer = BedrockFAISSIndexer()

        # Find all CSV and PDF files in data folder
        files = [f for f in os.listdir(data_dir) if f.lower().endswith('.csv') or f.lower().endswith('.pdf')]
        if not files:
            print("⚠️ No CSV or PDF files found in data directory.")
        for file in files:
            file_path = os.path.join(data_dir, file)
            if file.lower().endswith('.csv'):
                print(f"📊 Processing CSV file: {file_path}")
                indexer.process_csv(file_path)
                print("✅ CSV file processed successfully!")
            elif file.lower().endswith('.pdf'):
                print(f"📄 Processing PDF file: {file_path}")
                indexer.process_pdf(file_path)
                print("✅ PDF file processed successfully!")

        # Save the combined index
        print(f"💾 Saving combined index to: {index_path}")
        indexer.save_index(index_path)

        # Show statistics
        stats = indexer.get_stats()
        print("\n📊 Final Index Statistics:")
        print(f"   Total Documents: {stats['total_documents']}")
        print(f"   Index Size: {stats['index_size']}")
        print(f"   Dimension: {stats['dimension']}")
        print(f"   Sources: {stats['sources']}")

        print("\n🎉 Document processing completed successfully!")
        print("✅ Your FAISS index is ready for use with Streamlit!")

        return True

    except Exception as e:
        print(f"❌ Error processing documents: {e}")
        logging.error(f"Document processing failed: {e}")
        return False

def main():
    """Main function to process documents"""
    print("=" * 60)
    print("📚 Document Processing with AWS Bedrock FAISS")
    print("=" * 60)
    process_documents_to_faiss()
    print("\n🎯 Next Steps:")
    print("1. Run: streamlit run streamlit_bedrock.py")
    print("2. Your chatbot will use the processed FAISS index")
    print("3. Both CSV and PDF data will be searchable!")

if __name__ == "__main__":
    main() 