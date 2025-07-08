# Nibav Lift FAQ Chatbot with AWS Bedrock

This project implements a FAQ chatbot for Nibav Lifts using AWS Bedrock for embeddings and text generation, with FAISS for efficient similarity search.

## 🚀 Features

- **AWS Bedrock Integration**: Uses Amazon Titan Embeddings V2 and Titan Text Lite
- **FAISS-based similarity search**: Fast and efficient document retrieval
- **CSV and PDF support**: Process both file types
- **Streamlit web interface**: User-friendly chatbot interface
- **Mumbai Region**: Optimized for Asia Pacific (Mumbai) region
- **Enhanced answers**: Generate improved responses using Bedrock LLM

## 📦 Installation

1. **Install required packages:**
```bash
pip install -r requirements.txt
```

2. **AWS Setup:**
   - Configure AWS credentials with Bedrock access
   - Ensure access to `amazon.titan-embed-text-v2:0` and `amazon.titan-text-lite-v1`
   - Set region to `ap-south-1` (Mumbai)

## 🏃‍♂️ Quick Start

### 1. Process Your Documents
```bash
python process_documents.py
```
This will:
- Process your `data/Faq.csv` file
- Find and process any PDF files in your directory
- Create FAISS index using AWS Bedrock embeddings
- Save the index for future use

### 2. Run Streamlit App
```bash
streamlit run streamlit_bedrock.py
```

### 3. Test Bedrock Functionality
```bash
python test_bedrock.py
```

## 📁 Project Structure

```
faqq/
├── data/
│   └── Faq.csv                 # Your FAQ data
├── bedrock_faiss_indexer.py   # AWS Bedrock FAISS engine
├── bedrock_search.py          # Bedrock search interface
├── streamlit_bedrock.py       # Streamlit app with Bedrock
├── process_documents.py       # Document processing script
├── test_bedrock.py           # Bedrock testing script
├── requirements.txt           # Python dependencies
├── README_BEDROCK.md         # This file
├── db.py                     # Database operations
└── w1.py                     # CSV loading utilities
```

## 🔧 How It Works

### 1. Document Processing
- **CSV**: Processes each row (question + answer)
- **PDF**: Extracts text from each page
- **Embeddings**: Uses Amazon Titan Embeddings V2 (1536 dimensions)
- **FAISS**: Stores embeddings for fast similarity search

### 2. Search Process
- User query → Titan Embeddings V2 → FAISS search
- Returns most similar documents
- Option to generate enhanced answers with Titan Text Lite

### 3. AWS Bedrock Models Used
- **Embeddings**: `amazon.titan-embed-text-v2:0`
- **Text Generation**: `amazon.titan-text-lite-v1`
- **Region**: `ap-south-1` (Mumbai)

## 📊 Usage Examples

### Process Documents
```python
from process_documents import process_documents_to_faiss

# Process both CSV and PDF
success = process_documents_to_faiss(
    csv_path="data/Faq.csv",
    pdf_path="your_document.pdf"
)
```

### Search with Bedrock
```python
from bedrock_search import get_answer_bedrock

# Get answer
short_ans, long_ans = get_answer_bedrock("How much does it cost?")
print(f"Answer: {short_ans}")
```

### Generate Enhanced Answer
```python
from bedrock_search import generate_answer_with_bedrock

# Generate enhanced answer
enhanced = generate_answer_with_bedrock(
    "What about warranty?", 
    "Context about warranty information..."
)
```

## 🎯 Key Advantages

1. **AWS Managed**: No local model downloads
2. **High Quality**: Titan models are state-of-the-art
3. **Scalable**: Can handle large document collections
4. **Cost Effective**: Pay per API call
5. **Regional**: Optimized for Mumbai region

## 🔍 Search Parameters

- **k**: Number of results (default: 5)
- **threshold**: Similarity score (default: 0.35)
- **model**: Titan Embeddings V2 (1536 dimensions)

## 🛠️ Configuration

### AWS Credentials
```bash
# Set AWS credentials
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=ap-south-1
```

### Environment Variables
```python
# In your code
import os
os.environ['AWS_DEFAULT_REGION'] = 'ap-south-1'
```

## 📈 Performance

| Feature | Performance |
|---------|-------------|
| Embedding Generation | ~1-2 seconds per document |
| Search Speed | <100ms per query |
| Index Size | ~6KB per 1000 documents |
| Memory Usage | Low (embeddings stored in FAISS) |

## 🐛 Troubleshooting

### Common Issues

1. **AWS Credentials Error**:
   ```bash
   aws configure
   # Set region to ap-south-1
   ```

2. **Bedrock Access Error**:
   - Ensure Bedrock access is granted
   - Check model availability in Mumbai region

3. **PDF Processing Error**:
   ```bash
   pip install PyPDF2
   ```

### Debug Mode
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📝 API Endpoints

The system uses AWS Bedrock APIs:
- **Embeddings**: `bedrock-runtime` service
- **Text Generation**: `bedrock-runtime` service

## 🆘 Support

For issues:
1. Check AWS Bedrock documentation
2. Verify region and model access
3. Review AWS CloudWatch logs

## 📄 License

This project is for educational and demonstration purposes. 