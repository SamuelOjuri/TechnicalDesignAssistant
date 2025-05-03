import time
import random
from flask import current_app
from google import genai
from google.genai import types

# Define a function to check if an exception is a rate limit error
def is_rate_limit_error(exception):
    """Check if an exception is a rate limit error."""
    return '429' in str(exception) or 'RESOURCE_EXHAUSTED' in str(exception)

def gemini_api_with_retry(model, contents, max_retries=3, initial_backoff=2):
    """
    Call Gemini API with retry logic for rate limiting.
    
    Args:
        model: The Gemini model to use
        contents: The contents to send to the model
        max_retries: Maximum number of retries
        initial_backoff: Initial backoff time in seconds
    
    Returns:
        The model response
    """
    api_key = current_app.config.get('GOOGLE_API_KEY')
    client = genai.Client(api_key=api_key)
    
    retries = 0
    while retries <= max_retries:
        try:
            # Add a small random delay to help with rate limiting
            time.sleep(random.uniform(0.5, 1.5))
            
            # Make the API call
            response = client.models.generate_content(
                model=model,
                contents=contents
            )
            return response
        except Exception as e:
            # Check if this is a rate limiting error
            if is_rate_limit_error(e) and retries < max_retries:
                # Exponential backoff
                sleep_time = initial_backoff * (2 ** retries) + random.uniform(0, 1)
                print(f"Rate limit hit. Retrying in {sleep_time:.2f} seconds... (Attempt {retries + 1}/{max_retries})")
                time.sleep(sleep_time)
                retries += 1
                continue
            else:
                # For other errors, log and re-raise
                print(f"Error calling Gemini API: {str(e)}")
                raise e
    
    # If we've exhausted retries
    raise Exception(f"Failed to get response after {max_retries} retries")

def query_llm(context, query):
    """
    Sends the extracted text and query to Gemini.
    
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
    
    # Get response from Gemini
    model = current_app.config.get('GEMINI_MODEL', "gemini-2.5-flash-preview-04-17")
    response = gemini_api_with_retry(model, prompt)
    
    return response.text 