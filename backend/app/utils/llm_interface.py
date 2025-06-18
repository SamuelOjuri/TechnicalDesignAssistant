import time
import random
from flask import current_app
from google import genai
from google.genai import types
import logging

logger = logging.getLogger(__name__)

# Define a function to check if an exception is a rate limit error
def is_rate_limit_error(exception):
    """Check if an exception is a rate limit error."""
    return '429' in str(exception) or 'RESOURCE_EXHAUSTED' in str(exception) or 'RATE_LIMIT' in str(exception)

def gemini_api_with_retry(model, contents, max_retries=5, initial_backoff=5):
    """
    Call Gemini API with global rate limiting and enhanced retry logic.
    """
    from .rate_limiter import get_rate_limiter
    
    api_key = current_app.config.get('GOOGLE_API_KEY')
    client = genai.Client(api_key=api_key)
    rate_limiter = get_rate_limiter()
    
    retries = 0
    while retries <= max_retries:
        # Global rate limiting - wait for slot
        if not rate_limiter.wait_for_availability():
            raise Exception("Could not acquire API rate limit slot within timeout")
        
        try:
            logger.info(f"Making Gemini API call (attempt {retries + 1})")
            
            # Make the API call
            response = client.models.generate_content(
                model=model,
                contents=contents
            )
            
            # Success - release rate limiter
            rate_limiter.release()
            return response
            
        except Exception as e:
            # Always release the rate limiter slot
            rate_limiter.release()
            
            # Check if this is a rate limiting error
            if is_rate_limit_error(e) and retries < max_retries:
                # Enhanced exponential backoff with jitter
                base_sleep = initial_backoff * (2 ** retries)
                jitter = random.uniform(0, base_sleep * 0.1)
                sleep_time = base_sleep + jitter
                
                logger.warning(f"Rate limit hit. Retrying in {sleep_time:.2f} seconds... (Attempt {retries + 1}/{max_retries})")
                time.sleep(sleep_time)
                retries += 1
                continue
            else:
                logger.error(f"Error calling Gemini API: {str(e)}")
                raise e
    
    raise Exception(f"Failed to get response after {max_retries} retries due to rate limiting")

def query_llm(context, query):
    """
    Sends the extracted text and query to Gemini with rate limit protection.
    
    Args:
        context: The context information (e.g., extracted text)
        query: The query to send to the model
    
    Returns:
        str: The response text
    """
    # Construct a prompt that includes both the context and the query
    if not query:
        prompt = context
    else:
        prompt = f"""
        Please analyze the following information extracted from emails, PDF documents, and images:
        
        {context}
        
        QUESTION: {query}
        
        Note that information may be found in any of the content sources, including text from image descriptions.
        """
    
    # Get response from Gemini with enhanced retry logic
    model = current_app.config.get('GEMINI_MODEL', "gemini-2.5-flash")  
    response = gemini_api_with_retry(model, prompt)
    
    return response.text 