# AI Clinical Evidence Analyzer

A Streamlit-based application for analyzing clinical and medical questions using multi-source evidence aggregation, AI expert consultation, and RAGAS validation.

## Overview

This application helps researchers, clinicians, and healthcare professionals answer complex clinical questions by:

1. **Aggregating Evidence** - Searches PubMed, Google, and uploaded documents to gather comprehensive evidence
2. **RAG-Powered Analysis** - Uses vector stores (FAISS) with Azure OpenAI embeddings for intelligent retrieval
3. **Multi-Expert Consultation** - Consults 3 AI expert personas with different analytical perspectives
4. **RAGAS Validation** - Validates AI responses against source documents for faithfulness and quality
5. **Interactive Follow-ups** - Enables conversational follow-up questions with real-time web search augmentation
6. **Bottomline Answer** - Clear distinction between section of answer based on retrieved content and model's own knowledge
7. **Illustrative Diagram** - Python based without typos. :) 

## Features

### Evidence Aggregation
- **PubMed Integration**: Async search with MeSH term optimization and "cutting-edge" mode for recent research
- **Google Search**: Full-page content scraping with configurable result limits
- **Document Upload**: Support for PDF, DOCX, CSV, Excel, and images (with GPT-4 Vision analysis)
- **Vector Store**: FAISS indexing with configurable chunk sizes and relevance filtering

### Three Expert Personas

Each question is analyzed by 3 domain-specific AI experts:

| Expert | Focus | Approach |
|--------|-------|----------|
| **Expert 1** | Perspective 1 | Evidence-based |
| **Expert 2** | Perspective 2 | Risk/outcome minimization focused |
| **Expert 3** | Perspective 3 | Dense, information-rich responses |

Each expert provides:
- Rephrased domain-specific questions
- Bottom-line summary (1 paragraph)
- Detailed analysis (up to 4 paragraphs)
- Verification & confidence assessment
- Suggested Google Scholar searches

### RAGAS Validation

Validates AI responses using:
- **Faithfulness Score** (0-1): Claims supported by retrieved sources
- **Aspect Critic** (1-5): Custom bias/quality evaluation
- **Unsupported Assertions**: List of claims requiring additional verification

### Follow-up Questions

- Context-aware chat interface
- Real-time Google search integration
- Full conversation history
- Export thread as DOCX

### Export Options

- Download analysis as formatted DOCX
- Export expert opinions individually
- Download follow-up conversation threads
- Includes citations and hyperlinks

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  User Question  │────▶│ Medical Detection │────▶│ Search Strategy │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                        ┌─────────────────────────────────┼─────────────────────────────────┐
                        │                                 │                                 │
                        ▼                                 ▼                                 ▼
                ┌───────────────┐              ┌──────────────────┐              ┌──────────────────┐
                │ PubMed Search │              │  Google Search   │              │ Document Upload  │
                └───────┬───────┘              └────────┬─────────┘              └────────┬─────────┘
                        │                               │                                 │
                        └───────────────────────────────┼─────────────────────────────────┘
                                                        ▼
                                              ┌──────────────────┐
                                              │ FAISS Vector Store│
                                              └────────┬─────────┘
                                                       ▼
                                              ┌──────────────────┐
                                              │  LLM Processing  │
                                              │  (Iterative)     │
                                              └────────┬─────────┘
                                                       ▼
                        ┌──────────────────────────────┼──────────────────────────────┐
                        │                              │                              │
                        ▼                              ▼                              ▼
                ┌───────────────┐           ┌──────────────────┐           ┌──────────────────┐
                │RAGAS Validation│           │ Expert Personas  │           │ Follow-up Chat   │
                └───────────────┘           └──────────────────┘           └──────────────────┘
```

## Installation

### Prerequisites

- Python 3.11+
- Azure OpenAI API access
- Google Custom Search API credentials

### Local Setup

1. Clone the repository:
```bash
git clone https://github.com/your-org/gen-agent-public.git
cd gen-agent-public
```

2. Install dependencies using uv:
```bash
uv sync
```

Or using pip:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file or configure Streamlit secrets:
```plaintext
# Required
AZURE_OPENAI_API_KEY=your-azure-openai-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_DEPLOYMENT=gpt-4o
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-large
GOOGLE_API_KEY=your-google-api-key
GOOGLE_CSE_ID=your-custom-search-engine-id

# Optional
OPENAI_API_KEY=your-openai-key  # Fallback for vision/embeddings
PASSWORD=your-app-password       # Default: test_password
AZURE_VISION_DEPLOYMENT=gpt-4o  # For PDF image analysis
```

4. Run the application:
```bash
streamlit run app.py
```

### Docker Deployment

```bash
docker build -t clinical-analyzer .
docker run -p 8080:8501 \
  -e AZURE_OPENAI_API_KEY=xxx \
  -e AZURE_OPENAI_ENDPOINT=xxx \
  -e AZURE_DEPLOYMENT=gpt-4o \
  -e GOOGLE_API_KEY=xxx \
  -e GOOGLE_CSE_ID=xxx \
  clinical-analyzer
```

## Usage

### 1. Login

Enter the configured password to access the application.

### 2. Upload Documents (Optional)

Upload relevant documents to include in the analysis:
- **CSV/Excel**: Processed as dataframes for code-based analysis
- **PDF**: Text extraction with vision fallback for scanned documents
- **DOCX**: Full paragraph extraction
- **Images**: Analyzed using GPT-4 Vision

### 3. Configure Settings

Use the sidebar to configure:
- **LLM Model**: Select Azure OpenAI deployment
- **RAG Settings**: Chunk size, overlap, relevance threshold
- **Search Options**: Number of Google/PubMed results
- **Iteration Limit**: Code generation iterations (1-10)

### 4. Ask Your Question

Enter a clinical question. The system will:
1. Detect if it's a medical topic
2. Optimize search terms for PubMed
3. Gather evidence from multiple sources
4. Generate analysis with code execution
5. Display results with citations

### 5. Validate with RAGAS

Click "Validate Response" to check:
- Faithfulness against source documents
- Identify unsupported claims
- Get confidence scores

### 6. Consult Expert Personas

Click "Ask 3 AI Expert Personas" to receive:
- Three domain-specific expert perspectives
- Rephrased questions from each expert's viewpoint
- Comprehensive analysis with verification

### 7. Ask Follow-up Questions

Enable "Ask Follow-Up Questions" to:
- Continue the conversation with context
- Get real-time web search augmentation
- Export the full conversation thread

## Project Structure

```
gen-agent-public/
├── app.py                 # Main Streamlit application (4,800+ lines)
├── rag_utils.py           # RAG, search, and embedding utilities
├── search_utils.py        # Web search wrapper functions
├── document_utils.py      # Document processing (PDF, DOCX, images)
├── models.py              # Pydantic data models
├── prompts.py             # System prompts for experts and evaluation
├── markdown_to_docx.py    # DOCX export with formatting
├── pyproject.toml         # Project dependencies
├── Dockerfile             # Container configuration
└── .streamlit/
    └── config.toml        # Streamlit theme configuration
```

## Key Dependencies

| Package | Purpose |
|---------|---------|
| streamlit | Web application framework |
| langchain | LLM orchestration and chains |
| langchain-openai | Azure OpenAI integration |
| faiss-cpu | Vector similarity search |
| ragas | Response validation metrics |
| beautifulsoup4 | Web scraping |
| python-docx | DOCX generation |
| PyPDF2 | PDF text extraction |

## API Rate Limits

| Service | Limit | Notes |
|---------|-------|-------|
| Google Custom Search | 100/day (free) | Upgrade for higher limits |
| PubMed | No official limit | Use courteous delays |
| Azure OpenAI | Varies by quota | Check your deployment |

## Configuration

### Streamlit Theme

The app uses a dark theme by default. Modify `.streamlit/config.toml`:

```toml
[browser]
gatherUsageStats = false

[theme]
base = "dark"
```

### RAG Parameters

Default values (configurable in sidebar):
- **Chunk Size**: 1000 characters (scraped), 500 (snippets)
- **Chunk Overlap**: 200 characters (scraped), 50 (snippets)
- **Relevance Threshold**: 0.7
- **Max Results**: 5 documents per query

## Security Considerations

- Password protection on application entry
- API keys stored as environment variables
- File upload validation by type
- HTML escaping in document exports

**Important**: Never commit `.env` files or API keys to version control.

## Troubleshooting

### Common Issues

**"No embeddings model available"**
- Verify `AZURE_EMBEDDING_DEPLOYMENT` is set correctly
- Check Azure OpenAI endpoint accessibility

**"Google search failed"**
- Confirm `GOOGLE_API_KEY` and `GOOGLE_CSE_ID` are valid
- Check daily quota limits

**"PubMed search returned no results"**
- Try broader search terms
- Check network connectivity to NCBI

**PDF extraction issues**
- Ensure `poppler-utils` is installed (for pdf2image)
- Vision fallback requires valid OpenAI API key

## License

See [LICENSE](LICENSE) for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Acknowledgments

- Built with [Streamlit](https://streamlit.io/)
- Powered by [Azure OpenAI](https://azure.microsoft.com/en-us/products/ai-services/openai-service)
- Validated with [RAGAS](https://github.com/explodinggradients/ragas)
- Vector search by [FAISS](https://github.com/facebookresearch/faiss)

<img width="2238" height="1526" alt="CleanShot 2025-11-23 at 22 44 37@2x" src="https://github.com/user-attachments/assets/f49b0e2a-e703-4205-9049-c94942db5270" />
