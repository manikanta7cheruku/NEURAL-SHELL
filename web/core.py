"""
=============================================================================
PROJECT SEVEN - web/core.py (Web Search Engine)
Version: 1.4

PURPOSE:
    Searches the web using DuckDuckGo and returns clean text results
    that can be injected into the LLM prompt as context.
    
    No API key needed. Free. Privacy-focused.
=============================================================================
"""

from ddgs import DDGS
import colorama
from colorama import Fore

colorama.init(autoreset=True)


def web_search(query, max_results=2):
    """
    Search the web and return formatted results for LLM context.
    """
    print(Fore.CYAN + f"[WEB] Searching: '{query}'...")
    
    try:
        ddgs = DDGS()
        results_raw = ddgs.text(query, max_results=max_results)
        
        results = []
        for r in results_raw:
            title = r.get('title', '')
            body = r.get('body', '')
            href = r.get('href', '')
            
            if body:
                results.append({
                    'title': title,
                    'body': body,
                    'url': href
                })
        
        if not results:
            print(Fore.YELLOW + "[WEB] No results found.")
            return ""
        
        formatted = "=== WEB SEARCH RESULTS ===\n"
        formatted += f"Query: {query}\n"
        
        for i, r in enumerate(results, 1):
            formatted += f"\n[{i}] {r['title']}\n"
            formatted += f"    {r['body']}\n"
        
        formatted += "=== END WEB RESULTS ===\n"
        formatted += "Use these search results to answer the user's question accurately. "
        formatted += "Summarize naturally — do NOT dump raw results. "
        formatted += "If results don't answer the question, say what you found and that you couldn't find an exact answer."
        
        print(Fore.GREEN + f"[WEB] Found {len(results)} results.")
        return formatted
        
    except Exception as e:
        print(Fore.RED + f"[WEB] Search failed: {e}")
        return ""


def web_news(query, max_results=2):
    """
    Search for news specifically.
    """
    print(Fore.CYAN + f"[WEB] Searching news: '{query}'...")
    
    try:
        ddgs = DDGS()
        results_raw = ddgs.news(query, max_results=max_results)
        
        results = []
        for r in results_raw:
            title = r.get('title', '')
            body = r.get('body', '')
            date = r.get('date', '')
            source = r.get('source', '')
            
            if title:
                results.append({
                    'title': title,
                    'body': body,
                    'date': date,
                    'source': source
                })
        
        if not results:
            print(Fore.YELLOW + "[WEB] No news found.")
            return ""
        
        formatted = "=== LATEST NEWS ===\n"
        formatted += f"Topic: {query}\n"
        
        for i, r in enumerate(results, 1):
            formatted += f"\n[{i}] {r['title']}"
            if r['source']:
                formatted += f" ({r['source']})"
            if r['date']:
                formatted += f" — {r['date']}"
            formatted += f"\n    {r['body']}\n"
        
        formatted += "=== END NEWS ===\n"
        formatted += "Summarize these news items naturally for the user. Be concise."
        
        print(Fore.GREEN + f"[WEB] Found {len(results)} news items.")
        return formatted
        
    except Exception as e:
        print(Fore.RED + f"[WEB] News search failed: {e}")
        return ""