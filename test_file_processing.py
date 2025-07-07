#!/usr/bin/env python3
"""
Test script to verify file processing and CSV conversion
"""

import os
import pandas as pd
import glob

def test_csv_files():
    """Test the CSV files in the data directory"""
    
    print("🧪 Testing CSV Files in Data Directory")
    print("=" * 50)
    
    data_dir = "data"
    if not os.path.exists(data_dir):
        print("❌ Data directory not found")
        return
    
    # Find all CSV files
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    
    if not csv_files:
        print("❌ No CSV files found in data directory")
        return
    
    print(f"📁 Found {len(csv_files)} CSV files:")
    
    for csv_file in csv_files:
        filename = os.path.basename(csv_file)
        print(f"\n📄 File: {filename}")
        
        try:
            # Read CSV
            df = pd.read_csv(csv_file)
            
            print(f"   📊 Rows: {len(df)}")
            print(f"   📋 Columns: {list(df.columns)}")
            
            # Show sample data
            print(f"   📝 Sample Questions:")
            for i, row in df.head(3).iterrows():
                question = row.get('Question', 'N/A')
                answer = row.get('Concise Answer (bot default)', 'N/A')
                print(f"     {i+1}. Q: {question[:50]}...")
                print(f"        A: {answer[:50]}...")
            
            # Check for empty or duplicate content
            empty_questions = df['Question'].isna().sum()
            empty_answers = df['Concise Answer (bot default)'].isna().sum()
            
            if empty_questions > 0:
                print(f"   ⚠️  {empty_questions} empty questions found")
            if empty_answers > 0:
                print(f"   ⚠️  {empty_answers} empty answers found")
            
            # Check for duplicate questions
            duplicates = df['Question'].duplicated().sum()
            if duplicates > 0:
                print(f"   ⚠️  {duplicates} duplicate questions found")
            
        except Exception as e:
            print(f"   ❌ Error reading {filename}: {e}")
    
    print("\n✅ CSV file testing completed!")

def test_search_functionality():
    """Test the search functionality with sample queries"""
    
    print("\n🔍 Testing Search Functionality")
    print("=" * 50)
    
    # Import the search function
    try:
        from bedrock_search import get_answer_bedrock
        
        test_queries = [
            "What is nature?",
            "How does nature support the environment?",
            "What are forests?",
            "Tell me about AI",
            "What is machine learning?"
        ]
        
        for query in test_queries:
            print(f"\n🔍 Query: '{query}'")
            try:
                short_ans, long_ans = get_answer_bedrock(query, threshold=0.3)
                
                if short_ans:
                    print(f"   ✅ Found answer: {short_ans[:100]}...")
                    if long_ans:
                        print(f"   📖 Details available: {long_ans[:100]}...")
                else:
                    print(f"   ❌ No answer found")
                    
            except Exception as e:
                print(f"   ❌ Search error: {e}")
        
        print("\n✅ Search testing completed!")
        
    except ImportError:
        print("❌ Could not import search functions")

if __name__ == "__main__":
    test_csv_files()
    test_search_functionality() 