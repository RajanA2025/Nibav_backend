import faiss
import numpy as np
import pandas as pd
import pickle
import os
from sentence_transformers import SentenceTransformer
from typing import List, Tuple, Optional
import logging

# For PDF processing
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

class FAISSIndexer:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize FAISS indexer with sentence transformer model
        
        Args:
            model_name: Name of the sentence transformer model to use
        """
        self.model = SentenceTransformer(model_name)
        self.index = None
        self.documents = []
        self.document_metadata = []
        
    def process_csv(self, csv_path: str, text_column: str = "Question", 
                   answer_column: str = "Concise Answer (bot default)",
                   details_column: str = 'Details if user asks "Tell me more"') -> None:
        """
        Process CSV file and add to FAISS index
        
        Args:
            csv_path: Path to CSV file
            text_column: Column name for searchable text
            answer_column: Column name for concise answers
            details_column: Column name for detailed answers
        """
        try:
            df = pd.read_csv(csv_path)
            
            # Combine text for indexing (question + answer for better search)
            texts = []
            for _, row in df.iterrows():
                question = str(row.get(text_column, ""))
                answer = str(row.get(answer_column, ""))
                details = str(row.get(details_column, ""))
                
                # Combine question and answer for better search
                combined_text = f"{question} {answer}"
                texts.append(combined_text)
                
                # Store metadata
                self.documents.append({
                    'question': question,
                    'answer': answer,
                    'details': details,
                    'source': 'csv',
                    'row_index': len(self.documents)
                })
            
            # Create embeddings
            embeddings = self.model.encode(texts, show_progress_bar=True)
            
            # Initialize FAISS index
            dimension = embeddings.shape[1]
            self.index = faiss.IndexFlatIP(dimension)  # Inner product for cosine similarity
            
            # Normalize embeddings for cosine similarity
            faiss.normalize_L2(embeddings)
            
            # Add to index
            self.index.add(embeddings.astype('float32'))
            
            logging.info(f"✅ Successfully indexed {len(texts)} documents from CSV")
            
        except Exception as e:
            logging.error(f"❌ Error processing CSV: {str(e)}")
            raise
    
    def process_pdf(self, pdf_path: str) -> None:
        """
        Process PDF file and add to FAISS index
        
        Args:
            pdf_path: Path to PDF file
        """
        if not PDF_AVAILABLE:
            raise ImportError("PyPDF2 is required for PDF processing. Install with: pip install PyPDF2")
        
        try:
            texts = []
            
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num, page in enumerate(pdf_reader.pages):
                    text = page.extract_text()
                    if text.strip():
                        texts.append(text)
                        
                        # Store metadata
                        self.documents.append({
                            'text': text,
                            'source': 'pdf',
                            'page': page_num + 1,
                            'row_index': len(self.documents)
                        })
            
            if texts:
                # Create embeddings
                embeddings = self.model.encode(texts, show_progress_bar=True)
                
                # Initialize FAISS index if not exists
                if self.index is None:
                    dimension = embeddings.shape[1]
                    self.index = faiss.IndexFlatIP(dimension)
                
                # Normalize embeddings for cosine similarity
                faiss.normalize_L2(embeddings)
                
                # Add to index
                self.index.add(embeddings.astype('float32'))
                
                logging.info(f"✅ Successfully indexed {len(texts)} pages from PDF")
            else:
                logging.warning("⚠️ No text extracted from PDF")
                
        except Exception as e:
            logging.error(f"❌ Error processing PDF: {str(e)}")
            raise
    
    def search(self, query: str, k: int = 5, threshold: float = 0.3) -> List[Tuple[dict, float]]:
        """
        Search for similar documents
        
        Args:
            query: Search query
            k: Number of results to return
            threshold: Minimum similarity score
            
        Returns:
            List of tuples (document, score)
        """
        if self.index is None:
            raise ValueError("No index available. Please process documents first.")
        
        # Encode query
        query_embedding = self.model.encode([query])
        faiss.normalize_L2(query_embedding)
        
        # Search
        scores, indices = self.index.search(query_embedding.astype('float32'), k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if score >= threshold and idx < len(self.documents):
                results.append((self.documents[idx], float(score)))
        
        return results
    
    def save_index(self, index_path: str = "faiss_index") -> None:
        """
        Save FAISS index and documents to disk
        
        Args:
            index_path: Base path for saving files
        """
        if self.index is None:
            raise ValueError("No index to save")
        
        # Save FAISS index
        faiss.write_index(self.index, f"{index_path}.faiss")
        
        # Save documents metadata
        with open(f"{index_path}_documents.pkl", 'wb') as f:
            pickle.dump(self.documents, f)
        
        logging.info(f"✅ Index saved to {index_path}")
    
    def load_index(self, index_path: str = "faiss_index") -> None:
        """
        Load FAISS index and documents from disk
        
        Args:
            index_path: Base path for loading files
        """
        # Load FAISS index
        self.index = faiss.read_index(f"{index_path}.faiss")
        
        # Load documents metadata
        with open(f"{index_path}_documents.pkl", 'rb') as f:
            self.documents = pickle.load(f)
        
        logging.info(f"✅ Index loaded from {index_path}")
    
    def get_stats(self) -> dict:
        """
        Get index statistics
        
        Returns:
            Dictionary with index statistics
        """
        if self.index is None:
            return {"status": "No index available"}
        
        return {
            "total_documents": len(self.documents),
            "index_size": self.index.ntotal,
            "dimension": self.index.d,
            "sources": list(set(doc.get('source', 'unknown') for doc in self.documents))
        } 