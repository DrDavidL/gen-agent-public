"""
Utility functions for web search capabilities.
This module provides a wrapper around the RAG utilities.
"""

import streamlit as st

# Import models

# Import RAG utilities
from rag_utils import (
    get_reliable_rag_results,
    is_medical_topic,
    is_search_needed,
    get_follow_up_detection,
)


@st.cache_data(ttl=1800, show_spinner=False)
def web_search(
    query: str,
    max_results: int = None,
    include_date: bool = True,
    force_web: bool = False,
    compare_web: bool = False,
    use_pubmed: bool = False,
) -> str:
    """
    Perform a search using uploaded documents first, then fall back to web search.
    If compare_web is True, search both documents and web and compare results.
    Uses Streamlit caching to avoid redundant searches for the same query.

    For medical/health topics, the search will be biased toward reliable sites.

    Args:
        query: The search query string
        max_results: Maximum number of results to return (defaults to session state value)
        include_date: Whether to append today's date to the query (default: True)
        force_web: Force web search even if documents are available (default: False)
        compare_web: Compare document search results with web search results (default: False)

    Returns:
        A formatted string with search results or an error message.
        NOTE: This function returns a pre-formatted STRING, not a list or dictionary.

    Example:
        >>> search_results = web_search("latest news on climate change")
        >>> print(search_results)  # Already formatted, just print directly
    """
    # Use session state value if available, otherwise use default
    if max_results is None:
        max_results = st.session_state.get("rag_num_results", 5)

    # Check if web search is enabled
    use_web_search = st.session_state.get("use_web_search", True)
    doc_vector_store = st.session_state.get("document_vector_store")

    # Check for keywords that indicate we should use web search
    force_web_keywords = [
        "latest",
        "current",
        "recent",
        "news",
        "today",
        "update",
        "check web",
        "online",
        "internet",
    ]
    if any(keyword in query.lower() for keyword in force_web_keywords):
        force_web = True
        print(f"Using web search due to time-sensitive keywords in query: '{query}'")

    # Check if this is a medical query that might benefit from PubMed search
    is_medical_query = False
    if is_medical_topic(query):
        is_medical_query = True
        print(f"Detected medical topic in query: '{query}'")
        # If use_pubmed flag is set, we'll prioritize medical sources
        if use_pubmed:
            print(f"Using PubMed-optimized search for medical query: '{query}'")

    # If web search is disabled, don't force it unless explicitly requested
    if not use_web_search and not force_web and not compare_web:
        force_web = False
        print(f"Web search is disabled. Using only document search for: '{query}'")
    # Default to using web search if enabled
    elif use_web_search and not force_web and not compare_web:
        force_web = True
        print(f"Web search is enabled. Using web search for: '{query}'")

    # For comparison mode, we'll collect both document and web results
    document_results = None
    web_results = None

    # Try document vector store if available (either for comparison or if web search is disabled)
    if (
        doc_vector_store is not None
        and (not use_web_search or compare_web)
        and not force_web
    ):
        try:
            print(f"Searching DOCUMENT vector store for: '{query}'")

            # Query the document vector store
            k = st.session_state.get("rag_k_docs", 5)

            # Try with a higher k value to ensure we get results
            docs_and_scores = doc_vector_store.similarity_search_with_score(
                query, k=max(k, 10)
            )

            # If still no results, try with an even higher k and more general query
            if not docs_and_scores:
                print(
                    f"No results found with k={k}, trying with higher k value and more general query"
                )
                # Create a more general query by extracting key terms
                general_query = " ".join(
                    [
                        word
                        for word in query.lower().split()
                        if len(word) > 3
                        and word
                        not in [
                            "what",
                            "when",
                            "where",
                            "which",
                            "how",
                            "does",
                            "about",
                        ]
                    ]
                )
                docs_and_scores = doc_vector_store.similarity_search_with_score(
                    general_query, k=20
                )

            if docs_and_scores:
                # Format results
                formatted_results = (
                    f"Retrieved documents from UPLOADED FILES for query: '{query}'\n\n"
                )

                # Sort by relevance score (lower is better in FAISS)
                docs_and_scores.sort(key=lambda x: x[1])

                for i, (doc, score) in enumerate(docs_and_scores, 1):
                    source = doc.metadata.get("source", "Unknown")
                    doc_name = doc.metadata.get("document_name", "Unknown")
                    chunk = doc.metadata.get("chunk", "Unknown")

                    formatted_results += f"{i}. Score: {score:.4f}\n"
                    formatted_results += f"   Source: {source}\n"
                    formatted_results += (
                        f"   Title: Document {doc_name}, Chunk {chunk}\n"
                    )
                    formatted_results += f"   Content: {doc.page_content}\n\n"

                print(
                    f"Found {len(docs_and_scores)} relevant document chunks from uploaded documents"
                )
                # Add a clear indicator that documents were found with a more prominent header
                document_results = (
                    f"DOCUMENTS FOUND: {len(docs_and_scores)} relevant chunks in uploaded documents\n\n"
                    + formatted_results
                )

                # Add a summary of sources at the top for better visibility
                sources_summary = "Document Sources Summary:\n"
                unique_sources = set()
                for doc, _ in docs_and_scores:
                    source = doc.metadata.get("source", "Unknown")
                    unique_sources.add(source)

                for source in unique_sources:
                    sources_summary += f"- {source}\n"

                document_results = sources_summary + "\n" + document_results

                # If not in comparison mode, return document results
                if not compare_web:
                    return document_results
                # Otherwise continue to get web results for comparison
            else:
                print(
                    "No relevant documents found in uploaded documents for this specific query"
                )
                if not compare_web:
                    print(
                        "No relevant content found for this specific query. Documents ARE uploaded, but try different search terms or use 'Compare versus Web Search' for more information."
                    )
        except Exception as doc_error:
            print(f"Error searching document vector store: {doc_error}")
            print("Falling back to web search")

    # Get web search results (either as fallback or for comparison)
    try:
        # Always add current date to query for freshness
        from datetime import datetime

        current_date = datetime.now().strftime("%B %Y")  # Format: May 2025
        # Only add date if it's not already in the query
        if current_date.lower() not in query.lower():
            query = f"{query} {current_date}"
            print(f"Added current date to query: '{query}'")

        # Check if this is a follow-up question
        previous_questions = st.session_state.get("search_history", [])
        is_follow_up = get_follow_up_detection(query, previous_questions)

        # Get RAG results from web, with special handling for medical queries
        if is_medical_query and use_pubmed:
            # Use medical-specific search approach
            web_results = get_reliable_rag_results(
                query=query,
                follow_up=is_follow_up,
                num_results=max_results,
                medical_focus=True,
            )
        else:
            # Standard search approach
            web_results = get_reliable_rag_results(
                query=query, follow_up=is_follow_up, num_results=max_results
            )

        # Ensure web_results is a string
        if isinstance(web_results, dict):
            # Convert dictionary to formatted string
            formatted_results = f"Search results for: '{query}'\n\n"
            if "results" in web_results and isinstance(web_results["results"], list):
                for i, result in enumerate(web_results["results"], 1):
                    if isinstance(result, dict):
                        title = result.get("title", "No title")
                        url = result.get("url", "No URL")
                        snippet = result.get("snippet", "No snippet")
                        formatted_results += f"{i}. {title}\n"
                        formatted_results += f"   URL: {url}\n"
                        formatted_results += f"   {snippet}\n\n"
            web_results = formatted_results

        # If results contain an error message about vector store, fall back to direct Google search
        if "Error creating vector store" in web_results:
            print("Vector store creation failed, falling back to direct Google search")
            from rag_utils import google_search

            # Get direct search results
            search_results = google_search(query, max_results)

            if not search_results:
                web_results = "No web search results found."
            else:
                # Format results for display
                web_results = f"Search results for: '{query}'\n\n"
                for i, result in enumerate(search_results, 1):
                    title = str(result.get("title", ""))
                    link = str(result.get("link", ""))
                    snippet = str(result.get("snippet", ""))
                    web_results += f"{i}. {title}\n"
                    web_results += f"   URL: {link}\n"
                    web_results += f"   {snippet}\n\n"

        # If we're in comparison mode and have both document and web results
        if compare_web and document_results and web_results:
            # Create a comparison of the results
            comparison = create_search_comparison(query, document_results, web_results)
            return comparison

        # Otherwise return whichever results we have (document results have priority if available)
        return document_results if document_results else web_results
    except Exception as e:
        import traceback

        error_details = traceback.format_exc()
        print(f"Error in web_search: {error_details}")

        # Last resort fallback - try direct Google search
        try:
            from rag_utils import google_search

            search_results = google_search(query, max_results)

            if not search_results:
                return f"Error performing search and no results found: {str(e)}"

            formatted_results = f"Search results for: '{query}'\n\n"
            for i, result in enumerate(search_results, 1):
                title = str(result.title) if hasattr(result, "title") else ""
                link = str(result.link) if hasattr(result, "link") else ""
                snippet = str(result.snippet) if hasattr(result, "snippet") else ""
                formatted_results += f"{i}. {title}\n"
                formatted_results += f"   URL: {link}\n"
                formatted_results += f"   {snippet}\n\n"

            return formatted_results
        except Exception as fallback_error:
            return f"Error performing search: {str(e)}\nFallback error: {str(fallback_error)}"


def create_search_comparison(
    query: str, document_results: str, web_results: str
) -> str:
    """
    Create a comparison between document search results and web search results.

    Args:
        query: The original search query
        document_results: Formatted string of document search results
        web_results: Formatted string of web search results

    Returns:
        A formatted string comparing the two result sets
    """
    comparison = f"# Comparison of Search Results for: '{query}'\n\n"

    # Extract key information from document results
    doc_sources = []
    doc_content_snippets = []

    for line in document_results.splitlines():
        if line.strip().startswith("   Source:"):
            doc_sources.append(line.strip().replace("   Source:", "").strip())
        elif line.strip().startswith("   Content:"):
            # Get first 150 chars of content as snippet
            content = line.strip().replace("   Content:", "").strip()
            snippet = content[:150] + "..." if len(content) > 150 else content
            doc_content_snippets.append(snippet)

    # Extract key information from web results
    web_titles = []
    web_urls = []
    web_snippets = []

    if isinstance(web_results, str):
        for i, line in enumerate(web_results.splitlines()):
            if line.strip().startswith(tuple(f"{j}." for j in range(1, 11))):
                # This is a title line
                title = line.strip().split(". ", 1)[1] if ". " in line else line.strip()
                web_titles.append(title)
            elif line.strip().startswith("   URL:"):
                web_urls.append(line.strip().replace("   URL:", "").strip())
            elif i > 0 and not line.strip().startswith(
                ("   URL:", "   Source:", "   Title:")
            ):
                # This is likely a snippet
                if line.strip() and not line.strip().startswith(
                    tuple(f"{j}." for j in range(1, 11))
                ):
                    web_snippets.append(line.strip())
    elif isinstance(web_results, dict):
        # Handle dictionary format if that's what's returned
        if "results" in web_results and isinstance(web_results["results"], list):
            for result in web_results["results"]:
                if isinstance(result, dict):
                    if "title" in result:
                        web_titles.append(result["title"])
                    if "url" in result:
                        web_urls.append(result["url"])
                    if "snippet" in result:
                        web_snippets.append(result["snippet"])

    # Add document results section
    comparison += "## Document Search Results\n\n"
    if doc_sources:
        comparison += "### Sources:\n"
        for i, source in enumerate(doc_sources[:5]):  # Limit to first 5 sources
            comparison += f"- {source}\n"

        comparison += "\n### Content Snippets:\n"
        for i, snippet in enumerate(
            doc_content_snippets[:5]
        ):  # Limit to first 5 snippets
            comparison += f"- {snippet}\n"
    else:
        comparison += "No relevant results found in uploaded documents.\n"

    # Add web results section
    comparison += "\n## Web Search Results\n\n"
    if web_titles:
        comparison += "### Top Results:\n"
        for i in range(min(5, len(web_titles))):  # Limit to first 5 results
            if i < len(web_titles):
                comparison += f"- **{web_titles[i]}**\n"
            if i < len(web_urls):
                comparison += f"  URL: {web_urls[i]}\n"
            if i < len(web_snippets):
                comparison += f"  Snippet: {web_snippets[i]}\n"
    else:
        comparison += "No relevant results found from web search.\n"

    # Add comparison analysis
    comparison += "\n## Comparison Analysis\n\n"

    # Check if we have both document and web results to compare
    if doc_sources and web_titles:
        # Compare the content
        comparison += "### Key Differences:\n"
        comparison += "- Document results come from your uploaded files, while web results reflect publicly available information.\n"
        comparison += "- Document results may contain more specific or proprietary information relevant to your context.\n"
        comparison += "- Web results may contain more recent or broader information not available in your documents.\n\n"

        comparison += "### Recommendation:\n"
        comparison += "Consider both sources for a comprehensive understanding. Your documents may provide context-specific details, while web results offer broader or more current perspectives.\n"
    elif doc_sources:
        comparison += "Only document results were found. The information you're looking for appears to be contained in your uploaded documents but may not be widely available on the web.\n"
    elif web_titles:
        comparison += "Only web results were found. The information you're looking for doesn't appear to be in your uploaded documents but is available on the web.\n"
    else:
        comparison += "No results were found from either source. Consider refining your query or exploring different search terms.\n"

    # Include the full results for reference
    comparison += "\n## Full Document Search Results\n\n"
    comparison += document_results

    comparison += "\n## Full Web Search Results\n\n"
    comparison += web_results

    return comparison


# Re-export functions from rag_utils
# This allows existing code to continue using search_utils.is_search_needed without changes

if __name__ == "__main__":
    # Simple test if run directly
    test_query = "latest developments in AI"
    print(web_search(test_query))

    # Test the search detection
    test_questions = [
        "What is the capital of France?",
        "What are the latest developments in AI?",
        "How do I calculate the mean in pandas?",
        "What's happening in Ukraine right now?",
        "What is the current price of Bitcoin?",
        "How to sort a list in Python?",
    ]

    for q in test_questions:
        print(f"Question: '{q}' - Search needed: {is_search_needed(q)}")
