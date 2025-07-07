#!/usr/bin/env python3
"""
Simple test script for AWS Bedrock FAISS functionality
"""

import logging
from bedrock_faiss_indexer import BedrockFAISSIndexer
from bedrock_search import initialize_bedrock_index, get_answer_bedrock, generate_answer_with_bedrock

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_bedrock_csv():
    """Test Bedrock FAISS with CSV data"""
    print("🚀 Testing AWS Bedrock FAISS with CSV data...")
    
    try:
        # Initialize Bedrock FAISS index
        bedrock_indexer = initialize_bedrock_index("data/Faq.csv")
        
        # Get stats
        stats = bedrock_indexer.get_stats()
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
        
        print("\n🔍 Testing queries with Bedrock:")
        print("-" * 50)
        
        for query in test_queries:
            print(f"\n❓ Query: {query}")
            short_ans, long_ans = get_answer_bedrock(query)
            
            if short_ans:
                print(f"✅ Answer: {short_ans[:100]}...")
                
                # Test enhanced answer generation
                if long_ans:
                    print("🚀 Generating enhanced answer...")
                    enhanced = generate_answer_with_bedrock(query, f"Context: {short_ans} {long_ans}")
                    print(f"✨ Enhanced: {enhanced[:150]}...")
            else:
                print("❌ No answer found")
        
        print("\n✅ Bedrock FAISS test completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during Bedrock test: {e}")
        logging.error(f"Bedrock test failed: {e}")

def test_bedrock_search():
    """Test direct Bedrock FAISS search"""
    print("\n🔍 Testing direct Bedrock FAISS search...")
    
    try:
        bedrock_indexer = BedrockFAISSIndexer()
        bedrock_indexer.process_csv("data/Faq.csv")
        
        # Test search
        query = "warranty information"
        results = bedrock_indexer.search(query, k=3, threshold=0.3)
        
        print(f"\n❓ Query: {query}")
        print(f"📊 Found {len(results)} results:")
        
        for i, (doc, score) in enumerate(results, 1):
            print(f"\n{i}. Score: {score:.3f}")
            print(f"   Question: {doc['question']}")
            print(f"   Answer: {doc['answer'][:100]}...")
        
        print("\n✅ Direct Bedrock FAISS search test completed!")
        
    except Exception as e:
        print(f"❌ Error during direct search test: {e}")

if __name__ == "__main__":
    print("🧪 AWS Bedrock FAISS Testing Suite")
    print("=" * 50)
    
    # Test 1: CSV processing and search
    test_bedrock_csv()
    
    # Test 2: Direct search
    test_bedrock_search()
    
    print("\n🎉 All Bedrock tests completed!") 