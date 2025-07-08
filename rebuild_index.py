#!/usr/bin/env python3
"""
Simple script to rebuild the FAISS index with updated CSV files
"""

import os
import sys

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bedrock_faiss_indexer import BedrockFAISSIndexer

def rebuild_index():
    print("Rebuilding FAISS index...")
    
    data_dir = "data"
    index_path = "bedrock_faiss_index"
    
    # Initialize the indexer
    indexer = BedrockFAISSIndexer()
    
    # Process all CSV files in the data directory
    csv_files = [f for f in os.listdir(data_dir) if f.lower().endswith('.csv')]
    
    print(f"Found {len(csv_files)} CSV files to process:")
    for csv_file in csv_files:
        print(f"  - {csv_file}")
    
    # Process each CSV file
    for csv_file in csv_files:
        file_path = os.path.join(data_dir, csv_file)
        try:
            print(f"Processing {csv_file}...")
            indexer.process_csv(file_path)
            print(f"✓ Successfully processed {csv_file}")
        except Exception as e:
            print(f"✗ Error processing {csv_file}: {e}")
    
    # Save the index
    print("Saving index...")
    indexer.save_index(index_path)
    print("✓ Index saved successfully!")
    
    print("Index rebuild completed!")

if __name__ == "__main__":
    rebuild_index() 