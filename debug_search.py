#!/usr/bin/env python3
"""
Debug search functionality
"""

import logging
from bedrock_search import initialize_bedrock_index, get_answer_bedrock
from bedrock_faiss_indexer import BedrockFAISSIndexer

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def debug_search():
    """Debug the search functionality"""
    
    print("🔍 Debugging Search Functionality")
    print("=" * 50)
    
    try:
        # Load the existing index
        print("📂 Loading existing Bedrock FAISS index...")
        bedrock_indexer = initialize_bedrock_index()
        
        # Get stats
        stats = bedrock_indexer.get_stats()
        print(f"📊 Index Stats: {stats}")
        
        # Test different queries
        test_queries = [
            "warrenty",  # Your query
            "warranty",  # Correct spelling
            "How long is the warranty?",
            "What is the warranty period?",
            "warranty information",
            "How much does it cost?",
            "safety features"
        ]
        
        print("\n🔍 Testing queries with different thresholds:")
        print("-" * 50)
        
        for query in test_queries:
            print(f"\n❓ Query: '{query}'")
            
            # Test with different thresholds
            for threshold in [0.1, 0.2, 0.3, 0.35, 0.4]:
                short_ans, long_ans = get_answer_bedrock(query, threshold=threshold)
                
                if short_ans:
                    print(f"   ✅ Threshold {threshold}: Found answer")
                    print(f"   📝 Answer: {short_ans[:100]}...")
                    break
                else:
                    print(f"   ❌ Threshold {threshold}: No answer")
            
            # Test direct search
            print(f"   🔍 Direct search results:")
            results = bedrock_indexer.search(query, k=3, threshold=0.1)
            for i, (doc, score) in enumerate(results, 1):
                print(f"      {i}. Score: {score:.3f} | Source: {doc['source']}")
                if doc['source'] == 'csv':
                    print(f"         Q: {doc['question'][:50]}...")
                    print(f"         A: {doc['answer'][:50]}...")
                else:
                    print(f"         Text: {doc['text'][:50]}...")
        
        print("\n✅ Debug completed!")
        
    except Exception as e:
        print(f"❌ Error during debug: {e}")
        logging.error(f"Debug failed: {e}")

if __name__ == "__main__":
    debug_search() 