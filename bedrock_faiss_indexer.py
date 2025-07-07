import faiss
import numpy as np
import pandas as pd
import pickle
import os
import boto3
import json
from typing import List, Tuple, Optional
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# For PDF processing
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

class BedrockFAISSIndexer:
    def __init__(self, region_name: str = "ap-south-1", max_requests_per_second: int = 8):
        """
        Initialize FAISS indexer with AWS Bedrock embeddings (Mumbai region)
        
        Args:
            region_name: AWS region for Bedrock (ap-south-1 for Mumbai)
            max_requests_per_second: Rate limit for Bedrock API calls (default: 8 to be safe)
        """
        self.bedrock = boto3.client(
            service_name='bedrock-runtime',
            region_name=region_name
        )
        self.index = None
        self.documents = []
        self.max_requests_per_second = max_requests_per_second
        self.last_request_time = 0
        
    def _rate_limited_request(self):
        """Ensure we don't exceed rate limits"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        min_interval = 1.0 / self.max_requests_per_second
        
        if time_since_last < min_interval:
            sleep_time = min_interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
        
    def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding from AWS Bedrock using Titan Embeddings V2
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding
        """
        try:
            # Rate limiting
            self._rate_limited_request()
            
            # Using Amazon Titan Embeddings V2
            body = json.dumps({
                "inputText": text
            })
            
            response = self.bedrock.invoke_model(
                body=body,
                modelId="amazon.titan-embed-text-v2:0",
                accept="application/json",
                contentType="application/json"
            )
            
            response_body = json.loads(response.get('body').read())
            embedding = response_body['embedding']
            return embedding
            
        except Exception as e:
            logging.error(f"❌ Error getting embedding from Bedrock: {e}")
            raise
    
    def get_embeddings_batch_parallel(self, texts: List[str], max_workers: int = 4) -> np.ndarray:
        """
        Get embeddings for a batch of texts using parallel processing with rate limiting
        
        Args:
            texts: List of texts to embed
            max_workers: Number of parallel workers (keep low to respect rate limits)
            
        Returns:
            Numpy array of embeddings
        """
        embeddings = [None] * len(texts)
        
        def process_single_embedding(idx, text):
            try:
                embedding = self.get_embedding(text)
                return idx, embedding
            except Exception as e:
                logging.error(f"❌ Error processing text {idx}: {e}")
                return idx, None
        
        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_idx = {
                executor.submit(process_single_embedding, i, text): i 
                for i, text in enumerate(texts)
            }
            
            # Collect results
            for future in as_completed(future_to_idx):
                idx, embedding = future.result()
                if embedding is not None:
                    embeddings[idx] = embedding
                else:
                    logging.warning(f"⚠️ Failed to get embedding for text {idx}")
        
        # Filter out None values and convert to numpy array
        valid_embeddings = [emb for emb in embeddings if emb is not None]
        return np.array(valid_embeddings, dtype=np.float32)
    
    def get_embeddings_batch(self, texts: List[str]) -> np.ndarray:
        """
        Get embeddings for a batch of texts (sequential processing)
        
        Args:
            texts: List of texts to embed
            
        Returns:
            Numpy array of embeddings
        """
        embeddings = []
        for i, text in enumerate(texts):
            logging.info(f"📝 Processing text {i+1}/{len(texts)}")
            embedding = self.get_embedding(text)
            embeddings.append(embedding)
        
        return np.array(embeddings, dtype=np.float32)
        
    def process_csv(self, csv_path: str, text_column: str = "Question", 
                   answer_column: str = "Concise Answer (bot default)",
                   details_column: str = 'Details if user asks "Tell me more"') -> None:
        """
        Process CSV file and add to FAISS index using Bedrock embeddings (no chunking)
        """
        try:
            df = pd.read_csv(csv_path)
            texts = []
            for _, row in df.iterrows():
                question = str(row.get(text_column, ""))
                answer = str(row.get(answer_column, ""))
                details = str(row.get(details_column, ""))
                cleaned_answer = answer
                # ... cleaning code ...
                cleaned_answer = re.sub(r'^\d+\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^\d+\s*[A-Za-z]+\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^\d+\s*[A-Za-z]+\s+[A-Za-z]+\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^\d+\s*[A-Za-z]+\s+[A-Za-z]+\s+[A-Za-z]+\s*[?]?\s*', '', cleaned_answer)
                cleaned_answer = re.sub(r'^How long is the warranty\?\s*', '', cleaned_answer)
                cleaned_answer = re.sub(r'^What makes\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^Can I install\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^How much space\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^What is the\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^How many floors\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^How long does\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^Does it use\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^What safety\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^What happens\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^Is it noisy\?\s*', '', cleaned_answer)
                cleaned_answer = re.sub(r'^How often does\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^Can I customise\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^What does a\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^Where is\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^[A-Za-z\s]+\?\s*', '', cleaned_answer)
                cleaned_answer = cleaned_answer.strip()
                combined_text = f"{question} {cleaned_answer} {details}".strip()
                if combined_text:
                    texts.append(combined_text)
                    self.documents.append({
                        'question': question,
                        'answer': cleaned_answer,
                        'details': details,
                        'text': combined_text,
                        'source': 'csv',
                        'chunk': 1,
                        'row_index': len(self.documents)
                    })
            if texts:
                embeddings = self.get_embeddings_batch(texts)
                if self.index is None:
                    dimension = embeddings.shape[1]
                    self.index = faiss.IndexFlatIP(dimension)
                embeddings = embeddings.astype(np.float32)
                faiss.normalize_L2(embeddings)
                self.index.add(embeddings)
                logging.info(f"✅ Successfully indexed {len(texts)} CSV rows (no chunking)")
        except Exception as e:
            logging.error(f"❌ Error processing CSV: {str(e)}")
            raise
    
    def process_large_dataset(self, texts: List[str], chunk_size: int = 100, use_parallel: bool = True) -> None:
        """
        Process large datasets in chunks to handle memory and rate limit constraints
        
        Args:
            texts: List of all texts to process
            chunk_size: Number of texts to process in each chunk
            use_parallel: Whether to use parallel processing
        """
        total_texts = len(texts)
        logging.info(f"🚀 Processing large dataset: {total_texts} texts in chunks of {chunk_size}")
        
        for i in range(0, total_texts, chunk_size):
            chunk_texts = texts[i:i + chunk_size]
            chunk_start = i + 1
            chunk_end = min(i + chunk_size, total_texts)
            
            logging.info(f"📦 Processing chunk {chunk_start}-{chunk_end} of {total_texts}")
            
            try:
                # Get embeddings for this chunk
                if use_parallel:
                    embeddings = self.get_embeddings_batch_parallel(chunk_texts)
                else:
                    embeddings = self.get_embeddings_batch(chunk_texts)
                
                # Initialize index if needed
                if self.index is None:
                    dimension = embeddings.shape[1]
                    self.index = faiss.IndexFlatIP(dimension)
                    logging.info(f"🔧 Initialized FAISS index with dimension {dimension}")
                
                # Normalize and add to index
                embeddings = embeddings.astype(np.float32)
                faiss.normalize_L2(embeddings)
                self.index.add(embeddings)
                
                logging.info(f"✅ Added chunk {chunk_start}-{chunk_end} to index")
                
            except Exception as e:
                logging.error(f"❌ Error processing chunk {chunk_start}-{chunk_end}: {e}")
                raise
        
        logging.info(f"🎉 Successfully processed all {total_texts} texts")
    
    def process_csv_large(self, csv_path: str, text_column: str = "Question", 
                         answer_column: str = "Concise Answer (bot default)",
                         details_column: str = 'Details if user asks "Tell me more"',
                         chunk_size: int = 100) -> None:
        """
        Process large CSV files in chunks to handle memory constraints
        """
        try:
            df = pd.read_csv(csv_path)
            texts = []
            documents = []
            
            for _, row in df.iterrows():
                question = str(row.get(text_column, ""))
                answer = str(row.get(answer_column, ""))
                details = str(row.get(details_column, ""))
                cleaned_answer = answer
                # ... cleaning code ...
                cleaned_answer = re.sub(r'^\d+\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^\d+\s*[A-Za-z]+\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^\d+\s*[A-Za-z]+\s+[A-Za-z]+\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^\d+\s*[A-Za-z]+\s+[A-Za-z]+\s+[A-Za-z]+\s*[?]?\s*', '', cleaned_answer)
                cleaned_answer = re.sub(r'^How long is the warranty\?\s*', '', cleaned_answer)
                cleaned_answer = re.sub(r'^What makes\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^Can I install\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^How much space\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^What is the\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^How many floors\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^How long does\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^Does it use\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^What safety\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^What happens\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^Is it noisy\?\s*', '', cleaned_answer)
                cleaned_answer = re.sub(r'^How often does\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^Can I customise\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^What does a\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^Where is\s+', '', cleaned_answer)
                cleaned_answer = re.sub(r'^[A-Za-z\s]+\?\s*', '', cleaned_answer)
                cleaned_answer = cleaned_answer.strip()
                combined_text = f"{question} {cleaned_answer} {details}".strip()
                if combined_text:
                    texts.append(combined_text)
                    documents.append({
                        'question': question,
                        'answer': cleaned_answer,
                        'details': details,
                        'text': combined_text,
                        'source': 'csv',
                        'chunk': 1,
                        'row_index': len(documents)
                    })
            
            if texts:
                # Process in chunks
                self.process_large_dataset(texts, chunk_size=chunk_size)
                self.documents.extend(documents)
                logging.info(f"✅ Successfully indexed {len(texts)} CSV rows in chunks")
        except Exception as e:
            logging.error(f"❌ Error processing CSV: {str(e)}")
            raise
    
    def estimate_memory_usage(self, pdf_path: str) -> dict:
        """
        Estimate memory usage for processing a PDF file
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with memory estimates
        """
        if not PDF_AVAILABLE:
            return {"error": "PyPDF2 not available"}
        
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                
                # Sample first few pages to estimate chunks
                sample_pages = min(5, total_pages)
                total_chunks = 0
                total_text_length = 0
                
                for page_num in range(sample_pages):
                    page = pdf_reader.pages[page_num]
                    text = page.extract_text()
                    if text and text.strip():
                        cleaned_text = self._clean_pdf_text(text)
                        if cleaned_text.strip():
                            is_table = self._detect_table_content(cleaned_text)
                            if is_table:
                                chunks = self._chunk_text(cleaned_text, max_chunk_size=400, overlap=50)
                            else:
                                chunks = self._chunk_text(cleaned_text, max_chunk_size=300, overlap=150)
                            total_chunks += len(chunks)
                            total_text_length += len(cleaned_text)
                
                # Extrapolate to full document
                avg_chunks_per_page = total_chunks / sample_pages if sample_pages > 0 else 0
                estimated_total_chunks = avg_chunks_per_page * total_pages
                
                # Memory calculations
                embedding_size_bytes = estimated_total_chunks * 1536 * 4  # 1536 dims × 4 bytes
                metadata_size_bytes = estimated_total_chunks * 500  # ~500 bytes per doc
                total_memory_mb = (embedding_size_bytes + metadata_size_bytes) / (1024 * 1024)
                
                return {
                    "file_type": "pdf",
                    "total_pages": total_pages,
                    "estimated_chunks": int(estimated_total_chunks),
                    "estimated_memory_mb": round(total_memory_mb, 2),
                    "embedding_memory_mb": round(embedding_size_bytes / (1024 * 1024), 2),
                    "metadata_memory_mb": round(metadata_size_bytes / (1024 * 1024), 2),
                    "processing_time_minutes": round(estimated_total_chunks / 600, 1),  # 10 req/sec = 600/min
                    "estimated_cost_usd": round(estimated_total_chunks * 0.0001, 2)  # $0.10 per 1000
                }
                
        except Exception as e:
            return {"error": f"Error estimating memory: {str(e)}"}

    def estimate_csv_memory_usage(self, csv_path: str) -> dict:
        """
        Estimate memory usage for processing a CSV file
        
        Args:
            csv_path: Path to CSV file
            
        Returns:
            Dictionary with memory estimates
        """
        try:
            df = pd.read_csv(csv_path)
            total_rows = len(df)
            
            # Count non-empty text entries
            text_columns = []
            for col in df.columns:
                if df[col].dtype == 'object':  # Text columns
                    non_empty = df[col].notna().sum()
                    if non_empty > 0:
                        text_columns.append((col, non_empty))
            
            # Estimate total text entries (CSV processing doesn't chunk, one entry per row)
            total_text_entries = total_rows  # Each row becomes one text entry
            
            # Memory calculations
            embedding_size_bytes = total_text_entries * 1536 * 4  # 1536 dims × 4 bytes
            metadata_size_bytes = total_text_entries * 500  # ~500 bytes per doc
            total_memory_mb = (embedding_size_bytes + metadata_size_bytes) / (1024 * 1024)
            
            return {
                "file_type": "csv",
                "total_rows": total_rows,
                "text_columns": text_columns,
                "estimated_entries": total_text_entries,
                "estimated_memory_mb": round(total_memory_mb, 2),
                "embedding_memory_mb": round(embedding_size_bytes / (1024 * 1024), 2),
                "metadata_memory_mb": round(metadata_size_bytes / (1024 * 1024), 2),
                "processing_time_minutes": round(total_text_entries / 600, 1),  # 10 req/sec = 600/min
                "estimated_cost_usd": round(total_text_entries * 0.0001, 2),  # $0.10 per 1000
                "columns": list(df.columns)
            }
                
        except Exception as e:
            return {"error": f"Error estimating CSV memory: {str(e)}"}

    def process_pdf(self, pdf_path: str) -> None:
        """
        Process PDF file and add to FAISS index using Bedrock embeddings
        Handles both text-based and table-formatted PDFs
        """
        if not PDF_AVAILABLE:
            raise ImportError("PyPDF2 is required for PDF processing. Install with: pip install PyPDF2")
        try:
            texts = []
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages):
                    text = page.extract_text()
                    if text and text.strip():
                        cleaned_text = self._clean_pdf_text(text)
                        if cleaned_text.strip():
                            is_table = self._detect_table_content(cleaned_text)
                            if is_table:
                                chunks = self._chunk_text(cleaned_text, max_chunk_size=400, overlap=50)
                            else:
                                chunks = self._chunk_text(cleaned_text, max_chunk_size=300, overlap=150)
                            for chunk_idx, chunk in enumerate(chunks):
                                if chunk.strip() and len(chunk) > 20:
                                    texts.append(chunk)
                                    self.documents.append({
                                        'text': chunk,
                                        'source': 'pdf',
                                        'page': page_num + 1,
                                        'chunk': chunk_idx + 1,
                                        'row_index': len(self.documents),
                                        'is_table': is_table
                                    })
            if texts:
                embeddings = self.get_embeddings_batch(texts)
                if self.index is None:
                    dimension = embeddings.shape[1]
                    self.index = faiss.IndexFlatIP(dimension)
                embeddings = embeddings.astype(np.float32)
                faiss.normalize_L2(embeddings)
                self.index.add(embeddings)
                logging.info(f"✅ Successfully indexed {len(texts)} PDF chunks")
        except Exception as e:
            logging.error(f"❌ Error processing PDF: {str(e)}")
            raise
    
    def search(self, query: str, k: int = 5, threshold: float = 0.3) -> List[Tuple[dict, float]]:
        """
        Search for similar documents using Bedrock embeddings
        
        Args:
            query: Search query
            k: Number of results to return
            threshold: Minimum similarity score
            
        Returns:
            List of tuples (document, score)
        """
        if self.index is None:
            raise ValueError("No index available. Please process documents first.")
        
        # Encode query using Bedrock
        query_embedding = self.get_embedding(query)
        query_embedding = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query_embedding)
        
        # Search
        scores, indices = self.index.search(query_embedding, k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if score >= threshold and idx < len(self.documents):
                results.append((self.documents[idx], float(score)))
        
        return results
    
    def save_index(self, index_path: str = "bedrock_faiss_index") -> None:
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
    
    def load_index(self, index_path: str = "bedrock_faiss_index") -> None:
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
    
    def _chunk_text(self, text: str, max_chunk_size: int = 600, overlap: int = 100) -> List[str]:
        """
        Split text into overlapping chunks for better semantic search
        
        Args:
            text: Text to chunk
            max_chunk_size: Maximum size of each chunk
            overlap: Overlap between chunks
            
        Returns:
            List of text chunks
        """
        if len(text) <= max_chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + max_chunk_size
            
            # Try to break at semantic boundaries
            if end < len(text):
                # Priority 1: Look for paragraph breaks (double newlines)
                for i in range(end, max(start + max_chunk_size - 200, start), -1):
                    if text[i:i+2] == '\n\n':
                        end = i + 2
                        break
                
                # Priority 2: Look for sentence endings
                if end == start + max_chunk_size:
                    for i in range(end, max(start + max_chunk_size - 150, start), -1):
                        if text[i] in '.!?':
                            end = i + 1
                            break
                
                # Priority 3: Look for single newlines
                if end == start + max_chunk_size:
                    for i in range(end, max(start + max_chunk_size - 100, start), -1):
                        if text[i] == '\n':
                            end = i + 1
                            break
                
                # Priority 4: Look for common separators
                if end == start + max_chunk_size:
                    for i in range(end, max(start + max_chunk_size - 50, start), -1):
                        if text[i] in ';:':
                            end = i + 1
                            break
            
            chunk = text[start:end].strip()
            if chunk and len(chunk) > 20:  # Only meaningful chunks (reduced threshold for tables)
                chunks.append(chunk)
            
            start = end - overlap
            if start >= len(text):
                break
        
        return chunks 
    
    def _clean_pdf_text(self, text: str) -> str:
        """
        Clean and normalize PDF text for better processing
        
        Args:
            text: Raw text extracted from PDF
            
        Returns:
            Cleaned and normalized text
        """
        if not text:
            return ""
        
        # Remove excessive whitespace and normalize
        text = re.sub(r'\s+', ' ', text)
        
        # Handle table-like structures
        # Replace multiple spaces with single space (common in tables)
        text = re.sub(r' {2,}', ' ', text)
        
        # Handle line breaks in tables - convert to readable format
        text = re.sub(r'\n\s*\n', '\n\n', text)  # Multiple newlines to double newlines
        text = re.sub(r'([^\n])\n([^\n])', r'\1 \2', text)  # Single newlines to spaces
        
        # Clean up common PDF artifacts
        text = re.sub(r'[^\w\s\.\,\;\:\!\?\-\(\)\[\]\{\}\"\']+', ' ', text)
        
        # Remove page numbers and headers/footers
        text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)  # Standalone page numbers
        text = re.sub(r'Page \d+', '', text)  # Page headers
        text = re.sub(r'^\d+$', '', text, flags=re.MULTILINE)  # Standalone numbers
        
        # Clean up excessive punctuation
        text = re.sub(r'\.{2,}', '.', text)  # Multiple dots to single
        text = re.sub(r'\!{2,}', '!', text)  # Multiple exclamation marks
        text = re.sub(r'\?{2,}', '?', text)  # Multiple question marks
        
        # Normalize spacing around punctuation
        text = re.sub(r'\s+([\.\,\;\:\!\?])', r'\1', text)
        text = re.sub(r'([\.\,\;\:\!\?])\s*', r'\1 ', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        return text 
    
    def _detect_table_content(self, text: str) -> bool:
        """
        Detect if text contains table-like content
        
        Args:
            text: Text to analyze
            
        Returns:
            True if text appears to be table-formatted
        """
        if not text:
            return False
        
        # Count potential table indicators
        indicators = 0
        
        # Multiple consecutive spaces (column separators)
        if re.search(r' {3,}', text):
            indicators += 1
        
        # Multiple tabs
        if text.count('\t') > 2:
            indicators += 1
        
        # Regular line patterns (rows)
        lines = text.split('\n')
        if len(lines) > 3:
            # Check if lines have similar structure
            line_lengths = [len(line.strip()) for line in lines if line.strip()]
            if len(set(line_lengths)) <= len(line_lengths) * 0.3:  # Similar lengths
                indicators += 1
        
        # Numbers followed by text patterns (common in tables)
        if re.search(r'\d+\s+[A-Za-z]', text):
            indicators += 1
        
        # Multiple pipe characters or dashes (table borders)
        if text.count('|') > 5 or text.count('-') > 10:
            indicators += 1
        
        return indicators >= 2  # At least 2 indicators suggest table content 