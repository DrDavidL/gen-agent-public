"""
Utility functions for RAG (Retrieval Augmented Generation) capabilities.
"""

import os
from typing import List
import requests
import traceback
from langchain_community.vectorstores import FAISS
from langchain_openai import AzureOpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import streamlit as st
import re
from bs4 import BeautifulSoup
import logging
logger = logging.getLogger(__name__)
session = requests.Session()

# Import models
from models import SearchResult, DocumentMetadata

# Get API keys from environment
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", st.secrets.get("GOOGLE_API_KEY"))
GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID", st.secrets.get("GOOGLE_CSE_ID"))
AZURE_OPENAI_API_KEY = os.environ.get(
    "AZURE_OPENAI_API_KEY", st.secrets.get("AZURE_OPENAI_API_KEY")
)
AZURE_OPENAI_ENDPOINT = os.environ.get(
    "AZURE_OPENAI_ENDPOINT", st.secrets.get("AZURE_OPENAI_ENDPOINT")
)
AZURE_EMBEDDING_DEPLOYMENT = os.environ.get(
    "AZURE_EMBEDDING_DEPLOYMENT",
    st.secrets.get("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"),
)
AZURE_OPENAI_EMBEDDING_ENDPOINT = os.environ.get(
    "AZURE_OPENAI_EMBEDDING_ENDPOINT",
    st.secrets.get(
        "AZURE_OPENAI_EMBEDDING_ENDPOINT",
        "https://lab-secure.openai.azure.com/openai/deployments/text-embedding-3-large/embeddings?api-version=2023-05-15",
    ),
)

# Initialize session state for vector store if not already done
if "vector_store" not in st.session_state:
    st.session_state.vector_store = None
if "search_history" not in st.session_state:
    st.session_state.search_history = []


def scrape_webpage(url: str, timeout: int = 15) -> str:
    """
    Scrape content from a webpage.

    Args:
        url: The URL to scrape
        timeout: Request timeout in seconds

    Returns:
        Extracted text content from the webpage
    """
    try:
        # Use a more realistic user agent
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.google.com/",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }

        logger.debug(f"Sending request to: {url}")
        response = requests.get(url, headers=headers, timeout=timeout)

        # Check if the request was successful
        if response.status_code != 200:
            logger.debug(f"Failed to retrieve {url}: HTTP {response.status_code}")
            return f"Error: HTTP {response.status_code}"

        response.raise_for_status()

        # Check content type to ensure we're processing HTML
        content_type = response.headers.get("Content-Type", "").lower()
        if (
            "text/html" not in content_type
            and "application/xhtml+xml" not in content_type
        ):
            logger.debug(f"Skipping non-HTML content: {content_type} for {url}")
            return f"Skipped: Not HTML content ({content_type})"

        # Parse HTML content
        soup = BeautifulSoup(response.content, "html.parser")

        # Remove unwanted elements
        for element in soup(
            [
                "script",
                "style",
                "nav",
                "footer",
                "header",
                "aside",
                "iframe",
                "noscript",
            ]
        ):
            element.extract()

        # Try to find the main content area
        main_content = None
        for tag in [
            "main",
            "article",
            'div[role="main"]',
            "#content",
            "#main",
            ".main-content",
            ".article-content",
        ]:
            main_content = soup.select_one(tag)
            if main_content:
                logger.debug(f"Found main content using selector: {tag}")
                break

        # If main content area found, use it; otherwise use the whole body
        if main_content:
            text = main_content.get_text(separator=" ", strip=True)
        else:
            # Fallback to body content
            body = soup.find("body")
            if body:
                text = body.get_text(separator=" ", strip=True)
            else:
                text = soup.get_text(separator=" ", strip=True)

        # Clean up text (remove extra whitespace)
        text = re.sub(r"\s+", " ", text).strip()

        # Limit text length to avoid token limits
        max_chars = 15000
        if len(text) > max_chars:
            text = text[:max_chars] + "..."

        logger.debug(f"Successfully scraped {len(text)} characters from {url}")
        return text
    except requests.exceptions.Timeout:
        logger.debug(f"Timeout error scraping {url}")
        return f"Error: Timeout while scraping {url}"
    except requests.exceptions.TooManyRedirects:
        logger.debug(f"Too many redirects for {url}")
        return f"Error: Too many redirects for {url}"
    except requests.exceptions.RequestException as e:
        logger.debug(f"Request error scraping {url}: {e}")
        return f"Error: Request failed for {url}"
    except Exception as e:
        logger.debug(f"Error scraping {url}: {e}")
        return f"Error scraping content: {str(e)}"


@st.cache_data(ttl=1800, show_spinner=False)
def google_search(
    query: str, num_results: int = 10, scrape_content: bool = True
) -> List[SearchResult]:
    """
    Perform a Google search using the Custom Search JSON API.
    Uses Streamlit caching to avoid redundant API calls for the same query.

    Args:
        query: The search query string
        num_results: Number of results to return (max 10 per request)
        scrape_content: Whether to scrape full content from the webpages

    Returns:
        List of SearchResult objects with search results
    """
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        raise ValueError(
            "Google API key or CSE ID not found. Please set the GOOGLE_API_KEY and GOOGLE_CSE_ID environment variables."
        )

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "num": min(num_results, 10),  # API allows max 10 results per request
    }

    try:
        logger.debug(f"Performing Google search for: '{query}'")
        response = session.get(url, params=params)
        response.raise_for_status()
        search_results = response.json()

        results = []
        if "items" in search_results:
            logger.debug(f"Found {len(search_results['items'])} search results")
            for item in search_results["items"]:
                result = SearchResult(
                    title=item.get("title", ""),
                    link=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                )

                # Always try to scrape content if requested
                if scrape_content and result.link:
                    try:
                        logger.debug(f"Scraping content from {result.link}")
                        full_content = scrape_webpage(result.link)
                        if full_content and len(full_content) > len(result.snippet):
                            result.full_content = full_content
                            logger.debug(
                                f"Successfully scraped {len(full_content)} characters from {result.link}"
                            )
                        else:
                            logger.debug(
                                f"Scraping didn't yield useful content for {result.link}"
                            )
                    except Exception as scrape_error:
                        print(
                            f"Error scraping content from {result.link}: {scrape_error}"
                        )

                results.append(result)
        else:
            logger.debug(f"No search results found for query: '{query}'")
            if "error" in search_results:
                logger.debug(
                    f"Google API error: {search_results['error'].get('message', 'Unknown error')}"
                )

        return results
    except Exception as e:
        logger.debug(f"Error performing Google search: {e}")
        return []


@st.cache_resource(ttl=3600)
def get_embeddings_model():
    """
    Initialize and return the Azure OpenAI embeddings model.
    Uses Streamlit caching to avoid repeated initialization.
    """
    try:
        print(
            f"Initializing embeddings model with deployment: {AZURE_EMBEDDING_DEPLOYMENT}"
        )
        print(f"Azure endpoint: {AZURE_OPENAI_ENDPOINT}")

        if (
            not AZURE_OPENAI_API_KEY
            or not AZURE_OPENAI_ENDPOINT
            or not AZURE_EMBEDDING_DEPLOYMENT
        ):
            print("Missing required Azure OpenAI credentials for embeddings")
            return None

        # Clean up the endpoint URL to ensure it doesn't contain deployment or API version
        # base_endpoint = AZURE_OPENAI_EMBEDDING_ENDPOINT
        # if "/deployments/" in base_endpoint:
        #     base_endpoint = base_endpoint.split("/deployments/")[0]
        # if "?" in base_endpoint:
        #     base_endpoint = base_endpoint.split("?")[0]

        # # Remove trailing slash if present
        # if base_endpoint.endswith("/"):
        #     base_endpoint = base_endpoint[:-1]

        # print(f"Using base endpoint for embeddings: {base_endpoint}")

        embeddings = AzureOpenAIEmbeddings(
            azure_deployment=AZURE_EMBEDDING_DEPLOYMENT,
            openai_api_version="2024-02-01",
            azure_endpoint=AZURE_OPENAI_EMBEDDING_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
        )

        # Test the embeddings model with a simple string
        test_embedding = embeddings.embed_query("test")
        print(
            f"Embeddings model initialized successfully. Vector dimension: {len(test_embedding)}"
        )

        return embeddings
    except Exception as e:
        print(f"Error initializing embeddings model: {e}")
        print(f"Exception details: {traceback.format_exc()}")

        # Try fallback to OpenAI embeddings if Azure fails
        try:
            from langchain_openai import OpenAIEmbeddings

            print("Attempting fallback to OpenAI embeddings")
            openai_api_key = os.environ.get(
                "OPENAI_API_KEY", st.secrets.get("OPENAI_API_KEY")
            )
            if openai_api_key:
                embeddings = OpenAIEmbeddings(
                    model="text-embedding-3-large", openai_api_key=openai_api_key
                )
                test_embedding = embeddings.embed_query("test")
                print(
                    f"OpenAI embeddings initialized successfully. Vector dimension: {len(test_embedding)}"
                )
                return embeddings
        except Exception as fallback_error:
            print(f"Fallback to OpenAI embeddings also failed: {fallback_error}")

        return None


def create_vector_store_from_search(
    query: str,
    num_results: int = None,
    chunk_size: int = None,
    chunk_overlap: int = None,
):
    """
    Create a vector store from Google search results.

    Args:
        query: The search query string
        num_results: Number of search results to use (defaults to session state value)
        chunk_size: Size of text chunks for the vector store (defaults to session state value)
        chunk_overlap: Overlap between chunks (defaults to session state value)

    Returns:
        FAISS vector store and a formatted string with search results
    """
    # Use session state values if available, otherwise use defaults
    if num_results is None:
        num_results = st.session_state.get("rag_num_results", 10)
    if chunk_size is None:
        chunk_size = st.session_state.get("rag_chunk_size", 1000)
    if chunk_overlap is None:
        chunk_overlap = st.session_state.get("rag_chunk_overlap", 200)

    # Get scrape_content setting from session state
    scrape_content = st.session_state.get("rag_scrape_content", True)
    # Record this query in search history
    if "search_history" not in st.session_state:
        st.session_state.search_history = []
    if query not in st.session_state.search_history:
        st.session_state.search_history.append(query)

    # Always add current date information to the query
    from datetime import datetime

    current_date = datetime.now().strftime("%B %Y")  # Format: May 2025

    # Add date if not already included in the query
    if current_date.lower() not in query.lower():
        original_query = query
        query = f"{query} {current_date}"
        print(f"Updated query with current date: '{original_query}' → '{query}'")

    print(f"Creating vector store for query: '{query}'")

    # Get search results with content scraping based on settings
    search_results = google_search(query, num_results, scrape_content=scrape_content)

    if not search_results:
        print("No search results found.")
        return None, "No search results found."

    # Format results for display
    formatted_results = f"Search results for: '{query}'\n\n"
    for i, result in enumerate(search_results, 1):
        title = str(result.title) if hasattr(result, "title") else ""
        link = str(result.link) if hasattr(result, "link") else ""
        snippet = str(result.snippet) if hasattr(result, "snippet") else ""
        formatted_results += f"{i}. {title}\n"
        formatted_results += f"   URL: {link}\n"
        formatted_results += f"   {snippet}\n\n"

    # Create documents for vector store - with more robust error handling
    documents = []
    for i, result in enumerate(search_results):
        try:
            # Use full content if available, otherwise use snippet
            if hasattr(result, "full_content") and result.full_content:
                content_text = str(result.full_content)
                print(
                    f"Using full scraped content for result {i + 1}: {result.link} ({len(content_text)} chars)"
                )

                # Create a document with the full content
                content = f"Title: {result.title}\nURL: {result.link}\nContent: {content_text}"
                metadata = DocumentMetadata(
                    source=result.link, title=result.title, is_scraped=True
                )
                documents.append(
                    Document(page_content=content, metadata=metadata.model_dump())
                )
            else:
                # If no full content, use the snippet
                content_text = result.snippet
                print(
                    f"Using snippet for result {i + 1}: {result.link} ({len(content_text)} chars)"
                )

                # Create a document with just the snippet
                content = f"Title: {result.title}\nURL: {result.link}\nContent: {content_text}"
                metadata = DocumentMetadata(
                    source=result.link, title=result.title, is_scraped=False
                )
                documents.append(
                    Document(page_content=content, metadata=metadata.model_dump())
                )
        except Exception as doc_error:
            print(f"Error creating document from search result {i + 1}: {doc_error}")
            # Continue with other results
            continue

    # Skip empty documents to avoid errors
    if not documents:
        return None, "No valid documents found to create vector store."

    # Split documents into chunks with error handling
    try:
        print(f"Splitting {len(documents)} documents into chunks")

        # Use different chunk sizes based on whether the content is scraped or not
        scraped_docs = [
            doc for doc in documents if doc.metadata.get("is_scraped", False)
        ]
        snippet_docs = [
            doc for doc in documents if not doc.metadata.get("is_scraped", False)
        ]

        chunks = []

        # Process scraped documents with larger chunks
        if scraped_docs:
            print(f"Processing {len(scraped_docs)} documents with scraped content")
            text_splitter_scraped = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", ". ", " ", ""],
            )
            scraped_chunks = text_splitter_scraped.split_documents(scraped_docs)
            print(f"Created {len(scraped_chunks)} chunks from scraped content")
            chunks.extend(scraped_chunks)

        # Process snippet documents with smaller chunks
        if snippet_docs:
            print(f"Processing {len(snippet_docs)} documents with snippet content")
            # Use smaller chunks for snippets to avoid combining unrelated snippets
            text_splitter_snippets = RecursiveCharacterTextSplitter(
                chunk_size=500,  # Smaller chunk size for snippets
                chunk_overlap=50,  # Less overlap for snippets
                length_function=len,
                separators=["\n", ". ", " ", ""],
            )
            snippet_chunks = text_splitter_snippets.split_documents(snippet_docs)
            print(f"Created {len(snippet_chunks)} chunks from snippet content")
            chunks.extend(snippet_chunks)

        if not chunks:
            print("No valid chunks created from documents.")
            return None, "No valid chunks created from documents."

        print(f"Total chunks created: {len(chunks)}")

    except Exception as split_error:
        print(f"Error splitting documents: {split_error}")
        return None, f"Error splitting documents: {str(split_error)}"

    # Create vector store
    embeddings = get_embeddings_model()
    if not embeddings:
        return None, "Failed to initialize embeddings model."

    try:
        # Create a simple text document if we're having issues with the original documents
        if len(chunks) == 0:
            print("No chunks available, creating fallback document")
            # Create a fallback document with search results
            fallback_content = formatted_results
            fallback_doc = Document(
                page_content=fallback_content,
                metadata={
                    "source": "fallback",
                    "title": f"Search results for: {query}",
                },
            )
            chunks = [fallback_doc]

        # Debug information
        print(f"Creating vector store with {len(chunks)} chunks")

        # Print sample of chunks for debugging
        for i, chunk in enumerate(chunks[:3]):  # Print first 3 chunks only
            print(f"Chunk {i} sample (first 100 chars): {chunk.page_content[:100]}...")
            print(f"Chunk {i} metadata: {chunk.metadata}")

        # Create the vector store
        vector_store = FAISS.from_documents(chunks, embeddings)

        # Verify the vector store was created successfully
        if vector_store:
            print(f"Vector store created successfully with {len(chunks)} chunks")
            # Store in session state for future use
            st.session_state.vector_store = vector_store
            return vector_store, formatted_results
        else:
            print("Vector store creation returned None")
            return None, "Failed to create vector store"

    except Exception as e:
        print(f"Error creating vector store: {e}")
        print(f"Exception details: {traceback.format_exc()}")

        # Try a more basic approach if the first attempt failed
        try:
            print("Attempting fallback vector store creation with simplified documents")

            # Create simplified documents directly from search results
            simple_docs = []
            for i, result in enumerate(search_results):
                title = (
                    str(result.title)
                    if hasattr(result, "title") and result.title is not None
                    else f"Result {i}"
                )
                link = (
                    str(result.link)
                    if hasattr(result, "link") and result.link is not None
                    else ""
                )
                snippet = (
                    str(result.snippet)
                    if hasattr(result, "snippet") and result.snippet is not None
                    else ""
                )

                # Combine title and snippet for a simple document
                content = f"Title: {title}\nURL: {link}\nSummary: {snippet}"

                simple_docs.append(
                    Document(
                        page_content=content, metadata={"source": link, "title": title}
                    )
                )

            if simple_docs:
                print(
                    f"Creating fallback vector store with {len(simple_docs)} simplified documents"
                )
                vector_store = FAISS.from_documents(simple_docs, embeddings)
                st.session_state.vector_store = vector_store
                return vector_store, formatted_results

            return None, f"Error creating vector store: {str(e)}"
        except Exception as fallback_error:
            print(f"Fallback vector store creation also failed: {fallback_error}")
            return None, f"Error creating vector store: {str(e)}"


def query_vector_store(query: str, k: int = None):
    """
    Query the vector store for relevant documents.

    Args:
        query: The query string
        k: Number of documents to retrieve (defaults to session state value)

    Returns:
        List of retrieved documents and their scores
    """
    # Use session state value if available, otherwise use default
    if k is None:
        k = st.session_state.get("rag_k_docs", 5)
    if st.session_state.vector_store is None:
        return [], "Vector store not initialized. Please perform a search first."

    # Ensure query is a string
    query = str(query).strip()
    if not query:
        return [], "Empty query provided."

    try:
        # Ensure k is a positive integer
        k = max(1, int(k))
        docs_and_scores = st.session_state.vector_store.similarity_search_with_score(
            query, k=k
        )

        # Format results
        results = []
        formatted_results = f"Retrieved documents for query: '{query}'\n\n"

        if not docs_and_scores:
            return [], "No relevant documents found for this query."

        # Sort by relevance score (lower is better in FAISS)
        docs_and_scores.sort(key=lambda x: x[1])

        # Separate snippets and full content chunks
        snippets = []
        full_content_chunks = []

        for i, (doc, score) in enumerate(docs_and_scores):
            # Ensure all values are strings
            source = str(doc.metadata.get("source", "Unknown"))
            title = str(doc.metadata.get("title", "Unknown"))
            content = str(doc.page_content)
            is_scraped = doc.metadata.get("is_scraped", False)

            result_item = {
                "content": content,
                "source": source,
                "title": title,
                "score": score,
                "is_scraped": is_scraped,
            }

            # Add to appropriate list
            if is_scraped:
                full_content_chunks.append((i + 1, doc, score, result_item))
            else:
                snippets.append((i + 1, doc, score, result_item))

            results.append(result_item)

        # First add the full content chunks (sorted by relevance)
        for i, doc, score, _ in full_content_chunks:
            source = str(doc.metadata.get("source", "Unknown"))
            title = str(doc.metadata.get("title", "Unknown"))
            content = str(doc.page_content)

            formatted_results += f"{i}. Score: {score:.4f}\n"
            formatted_results += f"   Source: {source}\n"
            formatted_results += f"   Title: {title}\n"
            formatted_results += f"   Content: {content}\n\n"

        # Then add a combined snippets section if there are any snippets
        if snippets:
            formatted_results += "Combined Snippets:\n"
            formatted_results += "   Sources:\n"

            # List all snippet sources
            for i, doc, score, _ in snippets:
                source = str(doc.metadata.get("source", "Unknown"))
                title = str(doc.metadata.get("title", "Unknown"))
                formatted_results += f"   - {title} ({source}) [Score: {score:.4f}]\n"

            formatted_results += "   Content:\n"

            # Combine all snippet content
            combined_content = "\n".join(
                [
                    f"From {doc.metadata.get('title', 'Unknown')}: {doc.page_content.split('Content: ')[-1]}"
                    for _, doc, _, _ in snippets
                ]
            )

            formatted_results += f"   {combined_content}\n\n"

        return results, formatted_results
    except Exception as e:
        print(f"Error querying vector store: {e}")
        return [], f"Error querying vector store: {str(e)}"


def get_reliable_rag_results(
    query: str,
    follow_up: bool = False,
    num_results: int = None,
    medical_focus: bool = False,
):
    """
    Get RAG results using a reliable approach.

    Args:
        query: The query string
        follow_up: Whether this is a follow-up question
        num_results: Number of search results to use (defaults to session state value)

    Returns:
        Formatted string with search results and retrieved documents
    """
    # Use session state value if available, otherwise use default
    if num_results is None:
        num_results = st.session_state.get("rag_num_results", 10)
    # Validate inputs
    if not query or not isinstance(query, str):
        return "Error: Invalid query provided."

    try:
        # For follow-up questions, use the existing vector store
        if follow_up and st.session_state.vector_store is not None:
            # Query the existing vector store
            retrieved_docs, formatted_retrieval = query_vector_store(query)

            if not retrieved_docs:
                # If no relevant docs found for follow-up, create a new vector store
                vector_store, formatted_search = create_vector_store_from_search(
                    query, num_results
                )
                if vector_store:
                    retrieved_docs, formatted_retrieval = query_vector_store(query)
                    return f"{formatted_search}\n\n{formatted_retrieval}"
                else:
                    return formatted_search
            else:
                return formatted_retrieval
        else:
            # For new questions, create a new vector store
            # If medical_focus is True, prioritize medical sources
            if medical_focus:
                print(f"Using medical-focused search for query: '{query}'")
                # Add medical domain restrictions to the query
                medical_domains = "site:www.nih.gov OR site:www.ncbi.nlm.nih.gov OR site:www.cdc.gov OR site:www.who.int OR site:www.mayoclinic.org OR site:www.medscape.com OR site:www.uptodate.com OR site:www.nejm.org OR site:www.bmj.com OR site:www.thelancet.com"
                medical_query = f"{query} {medical_domains}"
                vector_store, formatted_search = create_vector_store_from_search(
                    medical_query, num_results
                )
            else:
                vector_store, formatted_search = create_vector_store_from_search(
                    query, num_results
                )

            if vector_store:
                retrieved_docs, formatted_retrieval = query_vector_store(query)
                return f"{formatted_search}\n\n{formatted_retrieval}"
            else:
                return formatted_search
    except Exception as e:
        error_msg = f"Error in RAG processing: {str(e)}"
        print(error_msg)
        return error_msg


@st.cache_data(ttl=3600, show_spinner=False)
def is_medical_topic(question: str) -> bool:
    """
    Determines if a question is related to medical/health topics.
    Uses Streamlit caching to avoid redundant processing of the same question.

    Args:
        question: The user's question

    Returns:
        Boolean indicating if the question is medical-related
    """
    medical_keywords = [
        "medical",
        "medicine",
        "health",
        "disease",
        "diagnosis",
        "treatment",
        "symptom",
        "symptoms",
        "drug",
        "medication",
        "therapy",
        "side effect",
        "side effects",
        "doctor",
        "hospital",
        "clinical",
        "patient",
        "prescription",
        "vaccine",
        "vaccination",
        "epidemic",
        "pandemic",
        "cancer",
        "diabetes",
        "cardiac",
        "heart",
        "stroke",
        "infection",
        "virus",
        "bacteria",
        "covid",
        "covid-19",
        "surgery",
        "surgical",
        "allergy",
        "allergies",
        "asthma",
        "blood pressure",
        "cholesterol",
        "mental health",
        "anxiety",
        "depression",
        "psychiatric",
        "psychology",
        "nutrition",
        "diet",
        "exercise",
        "fitness",
        "wellness",
        "prevention",
        "screening",
        "immunization",
        "acute",
        "chronic",
        "gout",
        "arthritis",
        "rheumatology",
        "ventilator",
        "pneumonia",
        "respiratory",
        "lung",
        "pulmonary",
        "antibiotic",
        "microbial",
        "pathogen",
        "intensive care",
        "icu",
        "hospital acquired",
        "nosocomial",
    ]

    # Check for specific medical conditions or procedures in the question
    specific_conditions = [
        "ventilator associated pneumonia",
        "vap",
        "hospital acquired pneumonia",
        "nosocomial infection",
        "mechanical ventilation",
    ]

    question_lower = question.lower()

    # Check for specific conditions first (exact phrases)
    for condition in specific_conditions:
        if condition in question_lower:
            return True

    # Then check for individual keywords
    return any(keyword in question_lower for keyword in medical_keywords)


@st.cache_data(ttl=3600, show_spinner=False)
def is_search_needed(question: str) -> bool:
    """
    Determines if a web search is likely needed to answer the question.
    Uses Streamlit caching to avoid redundant processing of the same question.

    Args:
        question: The user's question

    Returns:
        Boolean indicating if search is recommended
    """
    # Always search for medical topics
    if is_medical_topic(question):
        return True

    # Keywords that suggest current information is needed
    time_keywords = [
        "latest",
        "recent",
        "current",
        "today",
        "now",
        "update",
        "news",
        "2023",
        "2024",
        "2025",
        "this year",
        "this month",
        "this week",
        "happening",
        "trending",
        "development",
    ]

    # Topics that likely need up-to-date information
    current_topics = [
        "stock",
        "market",
        "price",
        "election",
        "war",
        "conflict",
        "technology",
        "weather",
        "climate",
        "event",
        "release",
        "launch",
        "announcement",
        "update",
        "version",
    ]

    question_lower = question.lower()

    # If any time-related keyword is present, require search
    if any(keyword in question_lower for keyword in time_keywords):
        return True

    # If any current topic is present, require search
    if any(topic in question_lower for topic in current_topics):
        return True

    # Check for questions about "what is happening" or similar
    if any(
        phrase in question_lower
        for phrase in [
            "what is happening",
            "what's happening",
            "what's going on",
            "what is going on",
        ]
    ):
        return True

    return False


def get_follow_up_detection(
    current_question: str, previous_questions: List[str]
) -> bool:
    """
    Detect if the current question is a follow-up to previous questions.

    Args:
        current_question: The current question
        previous_questions: List of previous questions

    Returns:
        Boolean indicating if the current question is likely a follow-up
    """
    if not previous_questions:
        return False

    # Simple heuristics for follow-up detection
    follow_up_indicators = [
        "also",
        "additionally",
        "furthermore",
        "moreover",
        "in addition",
        "and what about",
        "what about",
        "how about",
        "tell me more",
        "elaborate",
        "explain further",
        "continue",
        "go on",
        "proceed",
        "next",
        "then",
        "after that",
        "following that",
        "subsequently",
        "why",
        "how",
        "when",
        "where",
        "who",
        "which",
        "what",
        "whose",
        "can you",
        "could you",
        "would you",
        "will you",
        "should you",
        "is it",
        "are they",
        "was it",
        "were they",
        "has it",
        "have they",
        "does it",
        "do they",
        "did it",
        "did they",
    ]

    # Check if the question starts with a follow-up indicator
    current_lower = current_question.lower()
    if any(current_lower.startswith(indicator) for indicator in follow_up_indicators):
        return True

    # Check for pronouns that might refer to previous context
    pronouns = [
        "it",
        "this",
        "that",
        "these",
        "those",
        "they",
        "them",
        "their",
        "he",
        "she",
        "his",
        "her",
    ]
    if any(f" {pronoun} " in f" {current_lower} " for pronoun in pronouns):
        return True

    return False
