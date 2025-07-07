from bedrock_faiss_indexer import BedrockFAISSIndexer
import boto3
import json
import logging
import os
from typing import Tuple, Optional

# Global FAISS indexer instance
bedrock_indexer = None

def initialize_bedrock_index(csv_path: str = "data/Faq.csv", 
                           index_path: str = "bedrock_faiss_index",
                           force_rebuild: bool = False) -> BedrockFAISSIndexer:
    """
    Initialize FAISS index with AWS Bedrock - either load existing or create new
    
    Args:
        csv_path: Path to CSV file
        index_path: Path to save/load FAISS index
        force_rebuild: Force rebuild index even if exists
        
    Returns:
        BedrockFAISSIndexer instance
    """
    global bedrock_indexer
    
    # Check if index already exists
    index_file = f"{index_path}.faiss"
    documents_file = f"{index_path}_documents.pkl"
    
    if not force_rebuild and os.path.exists(index_file) and os.path.exists(documents_file):
        try:
            bedrock_indexer = BedrockFAISSIndexer()
            bedrock_indexer.load_index(index_path)
            return bedrock_indexer
        except Exception as e:
            pass
    
    # Create new index
    bedrock_indexer = BedrockFAISSIndexer()
    bedrock_indexer.process_csv(csv_path)
    bedrock_indexer.save_index(index_path)
    
    return bedrock_indexer

def get_answer_bedrock(user_query: str, threshold: float = 0.35) -> Tuple[Optional[str], Optional[str]]:
    """
    Get answer using Bedrock FAISS search
    
    Args:
        user_query: User's question
        threshold: Minimum similarity score
        
    Returns:
        Tuple of (concise_answer, detailed_answer) or (None, None)
    """
    global bedrock_indexer
    
    if bedrock_indexer is None:
        bedrock_indexer = initialize_bedrock_index()
    
    try:
        # Search for similar documents
        results = bedrock_indexer.search(user_query, k=3, threshold=threshold)
        
        if results:
            # Get best match
            best_doc, best_score = results[0]
            
            if best_doc['source'] == 'csv':
                return best_doc['answer'], best_doc['details']
            else:
                # For PDF documents, return the text
                return best_doc['text'], best_doc['text']
        
        return None, None
        
    except Exception as e:
        logging.error(f"❌ Error in Bedrock search: {e}")
        return None, None

def generate_answer_with_bedrock(user_query: str, context: str) -> str:
    """
    Generate answer using Bedrock Titan Text Lite model
    
    Args:
        user_query: User's question
        context: Context information from FAISS search
        
    Returns:
        Generated answer
    """
    try:
        bedrock = boto3.client(
            service_name='bedrock-runtime',
            region_name='ap-south-1'
        )
        
        # Create prompt with context
        prompt = f"""Based on the following context about Nibav Lifts, answer the user's question.

Context: {context}

User Question: {user_query}

Please provide a helpful and accurate answer based on the context provided. If the context doesn't contain enough information to answer the question, please say so.

Answer:"""
        
        body = json.dumps({
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": 512,
                "stopSequences": [],
                "temperature": 0.7,
                "topP": 0.9
            }
        })
        
        response = bedrock.invoke_model(
            body=body,
            modelId="amazon.titan-text-lite-v1",
            accept="application/json",
            contentType="application/json"
        )
        
        response_body = json.loads(response.get('body').read())
        generated_text = response_body['results'][0]['outputText']
        
        return generated_text.strip()
        
    except Exception as e:
        logging.error(f"❌ Error generating answer with Bedrock: {e}")
        return "I apologize, but I'm unable to generate an answer at the moment."

def add_pdf_to_bedrock_index(pdf_path: str, index_path: str = "bedrock_faiss_index") -> bool:
    """
    Add PDF file to existing Bedrock FAISS index
    
    Args:
        pdf_path: Path to PDF file
        index_path: Path to FAISS index
        
    Returns:
        True if successful, False otherwise
    """
    global bedrock_indexer
    
    try:
        if bedrock_indexer is None:
            bedrock_indexer = initialize_bedrock_index(index_path=index_path)
        
        bedrock_indexer.process_pdf(pdf_path)
        bedrock_indexer.save_index(index_path)
        return True
        
    except Exception as e:
        logging.error(f"❌ Error adding PDF to Bedrock index: {e}")
        return False

def get_bedrock_index_stats() -> dict:
    """
    Get statistics about the Bedrock FAISS index
    
    Returns:
        Dictionary with index statistics
    """
    global bedrock_indexer
    
    if bedrock_indexer is None:
        return {"status": "No index initialized"}
    
    return bedrock_indexer.get_stats()

# Backward compatibility functions
def get_answer(user_query, questions=None, concise=None, detailed=None):
    """Backward compatibility wrapper"""
    return get_answer_bedrock(user_query) 