# Nibav Lift FAQ Chatbot with FAISS

This project implements a FAQ chatbot for Nibav Lifts using FAISS (Facebook AI Similarity Search) for efficient similarity search and retrieval.

## 🚀 Features

- **FAISS-based similarity search** - Fast and efficient document retrieval
- **CSV and PDF support** - Process both CSV files and PDF documents
- **Streamlit web interface** - User-friendly chatbot interface
- **FastAPI backend** - RESTful API for integration
- **User tracking** - Store user interactions and analytics
- **Real-time search** - Instant answers with semantic matching

## 📦 Installation

1. **Install required packages:**
```bash
pip install -r requirements.txt
```

2. **Or install manually:**
```bash
pip install streamlit pandas sentence-transformers streamlit-autorefresh faiss-cpu PyPDF2 fastapi pydantic uvicorn
```

## 🏃‍♂️ Quick Start

### 1. Test FAISS Functionality
```bash
python test_faiss_simple.py
```

### 2. Run Streamlit App (FAISS Version)
```bash
streamlit run streamlit_faiss.py
```

### 3. Run Original Streamlit App
```bash
streamlit run test.py
```

### 4. Run FastAPI Backend
```bash
uvicorn main:app --reload
```

## 📁 Project Structure

```
faqq/
├── data/
│   └── Faq.csv                 # FAQ data
├── faiss_indexer.py           # FAISS indexing and search
├── w3_faiss.py               # FAISS-based search functions
├── streamlit_faiss.py        # Streamlit app with FAISS
├── test_faiss_simple.py      # FAISS testing script
├── requirements.txt           # Python dependencies
├── README_FAISS.md           # This file
├── test.py                   # Original Streamlit app
├── main.py                   # FastAPI backend
├── db.py                     # Database operations
└── w1.py                     # CSV loading utilities
```

## 🔧 How It Works

### FAISS Indexing Process

1. **Document Processing**: 
   - CSV files are processed row by row
   - PDF files are processed page by page
   - Text is combined for better search results

2. **Embedding Generation**:
   - Uses `sentence-transformers` (all-MiniLM-L6-v2)
   - Creates 384-dimensional embeddings
   - Normalizes for cosine similarity

3. **FAISS Index**:
   - Uses `IndexFlatIP` for inner product similarity
   - Stores embeddings in memory for fast retrieval
   - Supports saving/loading for persistence

### Search Process

1. **Query Processing**: User query is converted to embedding
2. **Similarity Search**: FAISS finds most similar documents
3. **Threshold Filtering**: Only returns results above similarity threshold
4. **Response Generation**: Returns concise and detailed answers

## 📊 Usage Examples

### Basic FAISS Usage

```python
from faiss_indexer import FAISSIndexer

# Initialize indexer
indexer = FAISSIndexer()

# Process CSV file
indexer.process_csv("data/Faq.csv")

# Search for answers
results = indexer.search("How much does it cost?", k=3, threshold=0.3)

# Save index for later use
indexer.save_index("my_index")
```

### Adding PDF Documents

```python
# Add PDF to existing index
from w3_faiss import add_pdf_to_index

success = add_pdf_to_index("document.pdf")
if success:
    print("PDF added successfully!")
```

### Using the Search Function

```python
from w3_faiss import get_answer_faiss

# Get answer for user query
short_ans, long_ans = get_answer_faiss("What about warranty?")
print(f"Short: {short_ans}")
print(f"Detailed: {long_ans}")
```

## 🎯 Key Advantages of FAISS

1. **Speed**: Much faster than traditional similarity search
2. **Scalability**: Can handle large document collections
3. **Memory Efficient**: Optimized for large-scale operations
4. **Persistence**: Can save and load indexes
5. **Flexibility**: Supports multiple document types

## 🔍 Search Parameters

- **k**: Number of results to return (default: 5)
- **threshold**: Minimum similarity score (default: 0.3)
- **model**: Sentence transformer model (default: all-MiniLM-L6-v2)

## 📈 Performance Comparison

| Method | Speed | Memory | Scalability |
|--------|-------|--------|-------------|
| Original (w3.py) | Slow | High | Limited |
| FAISS (w3_faiss.py) | Fast | Low | High |

## 🛠️ Customization

### Change Similarity Threshold
```python
# In w3_faiss.py
short_ans, long_ans = get_answer_faiss(user_query, threshold=0.4)
```

### Use Different Model
```python
# In faiss_indexer.py
indexer = FAISSIndexer(model_name="all-mpnet-base-v2")
```

### Add Custom Document Types
```python
# Extend FAISSIndexer class
def process_txt(self, txt_path: str):
    # Add your custom text processing logic
    pass
```

## 🐛 Troubleshooting

### Common Issues

1. **FAISS Installation Error**:
   ```bash
   pip install faiss-cpu  # For CPU-only
   # or
   pip install faiss-gpu  # For GPU support
   ```

2. **Memory Issues**: Reduce batch size in embedding generation

3. **Low Search Quality**: Adjust threshold or use different model

### Debug Mode
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📝 API Endpoints (FastAPI)

- `GET /`: Welcome message
- `POST /register`: Register user
- `POST /ask`: Ask question and get answer

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Add tests
4. Submit pull request

## 📄 License

This project is for educational and demonstration purposes.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the test scripts
3. Check FAISS documentation: https://github.com/facebookresearch/faiss 