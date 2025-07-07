#!/usr/bin/env python3
"""
Test script to verify FAISS index functionality
"""

import os
import glob
from bedrock_faiss_indexer import BedrockFAISSIndexer

def test_index_functionality():
    """Test the index functionality"""
    
    print("🧪 Testing FAISS Index Functionality")
    print("=" * 50)
    
    # Check data directory
    data_dir = "data"
    if not os.path.exists(data_dir):
        print("❌ Data directory not found")
        return
    
    # List all files
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    pdf_files = glob.glob(os.path.join(data_dir, "*.pdf"))
    all_files = csv_files + pdf_files
    
    print(f"📁 Found {len(all_files)} files in data directory:")
    for file in all_files:
        print(f"   - {os.path.basename(file)}")
    
    if not all_files:
        print("❌ No files found to process")
        return
    
    # Create indexer
    print("\n🔧 Creating FAISS indexer...")
    indexer = BedrockFAISSIndexer()
    
    # Process all files
    print("\n📝 Processing files...")
    for file in all_files:
        try:
            if file.lower().endswith(".csv"):
                print(f"   Processing CSV: {os.path.basename(file)}")
                indexer.process_csv(file)
            elif file.lower().endswith(".pdf"):
                print(f"   Processing PDF: {os.path.basename(file)}")
                indexer.process_pdf(file)
        except Exception as e:
            print(f"   ❌ Error processing {os.path.basename(file)}: {e}")
    
    # Get stats
    stats = indexer.get_stats()
    print(f"\n📊 Index Statistics:")
    print(f"   Total documents: {stats.get('total_documents', 0)}")
    print(f"   Index size: {stats.get('index_size', 0)}")
    print(f"   Dimension: {stats.get('dimension', 0)}")
    print(f"   Sources: {stats.get('sources', [])}")
    
    # Test search
    print("\n🔍 Testing search functionality...")
    test_queries = [
        "What is AI?",
        "How does machine learning work?",
        "Tell me about lifts",
        "What are the benefits?"
    ]
    
    for query in test_queries:
        print(f"\n   Query: '{query}'")
        try:
            results = indexer.search(query, k=2, threshold=0.1)
            print(f"   Found {len(results)} results")
            for i, (doc, score) in enumerate(results):
                source = doc.get('source', 'unknown')
                if source == 'csv':
                    answer = doc.get('answer', '')[:100] + "..." if len(doc.get('answer', '')) > 100 else doc.get('answer', '')
                    print(f"     {i+1}. Score: {score:.3f}, Source: {source}, Answer: {answer}")
                else:
                    text = doc.get('text', '')[:100] + "..." if len(doc.get('text', '')) > 100 else doc.get('text', '')
                    print(f"     {i+1}. Score: {score:.3f}, Source: {source}, Text: {text}")
        except Exception as e:
            print(f"   ❌ Search error: {e}")
    
    print("\n✅ Test completed!")

if __name__ == "__main__":
    test_index_functionality() 