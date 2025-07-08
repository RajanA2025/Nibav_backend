#!/usr/bin/env python3
"""
Simple test script for FAISS functionality
"""

import logging
from faiss_indexer import FAISSIndexer
from w3_faiss import initialize_faiss_index, get_answer_faiss

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_faiss_csv():
    """Test FAISS with CSV data"""
    print("🚀 Testing FAISS with CSV data...")
    
    try:
        # Initialize FAISS index
        faiss_indexer = initialize_faiss_index("data/Faq.csv")
        
        # Get stats
        stats = faiss_indexer.get_stats()
        print(f"📊 Index Stats: {stats}")
        
        # Test some queries
        test_queries = [
            "How much does it cost?",
            "What about safety features?",
            "How long does installation take?",
            "Is it noisy?",
            "What happens during power cut?",
            "How much space do I need?",
            "What is the warranty period?",
            "Can I customize the color?"
        ]
        
        print("\n🔍 Testing queries:")
        print("-" * 50)
        
        for query in test_queries:
            print(f"\n❓ Query: {query}")
            short_ans, long_ans = get_answer_faiss(query)
            
            if short_ans:
                print(f"✅ Answer: {short_ans[:100]}...")
            else:
                print("❌ No answer found")
        
        print("\n✅ FAISS test completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during FAISS test: {e}")
        logging.error(f"FAISS test failed: {e}")

def test_faiss_search():
    """Test direct FAISS search"""
    print("\n🔍 Testing direct FAISS search...")
    
    try:
        faiss_indexer = FAISSIndexer()
        faiss_indexer.process_csv("data/Faq.csv")
        
        # Test search
        query = "warranty information"
        results = faiss_indexer.search(query, k=3, threshold=0.3)
        
        print(f"\n❓ Query: {query}")
        print(f"📊 Found {len(results)} results:")
        
        for i, (doc, score) in enumerate(results, 1):
            print(f"\n{i}. Score: {score:.3f}")
            print(f"   Question: {doc['question']}")
            print(f"   Answer: {doc['answer'][:100]}...")
        
        print("\n✅ Direct FAISS search test completed!")
        
    except Exception as e:
        print(f"❌ Error during direct search test: {e}")

if __name__ == "__main__":
    print("🧪 FAISS Testing Suite")
    print("=" * 50)
    
    # Test 1: CSV processing and search
    test_faiss_csv()
    
    # Test 2: Direct search
    test_faiss_search()
    
    print("\n🎉 All tests completed!") 