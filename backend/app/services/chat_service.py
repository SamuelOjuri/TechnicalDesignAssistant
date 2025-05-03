from flask import current_app
from ..utils.llm_interface import gemini_api_with_retry

def generate_chat_response(message, params=None, extracted_text=None):
    """
    Generate a response to a chat message based on the extracted parameters and text.
    
    Args:
        message: The user's message
        params: The extracted parameters dictionary
        extracted_text: The raw extracted text
    
    Returns:
        str: The generated response
    """
     # Debug logging to verify extracted_text is received
    print(f"Received extracted_text: {extracted_text[:100]}...")  # Print first 100 chars

    # If we don't have any parameters, return a message asking to process files first
    if not params:
        return "Please process files first to extract parameters."
    
    # Build system context
    params_text = "\n".join(f"• **{k}**: {v}" for k, v in params.items())
    raw_text = extracted_text or ""
    
    system = (
        "You are a roofing‑design assistant. Use the parameters below when answering; "
        "ask clarifying questions only when necessary.\n\n" + params_text + 
        "\n\nRaw extracted text from documents:\n" + raw_text
    )
    
    # Use configured model from app config
    model = current_app.config.get('GEMINI_MODEL', "gemini-2.5-flash-preview-04-17")
    
    # Call Gemini API with retry logic
    response = gemini_api_with_retry(model, [system, message])
    
    return response.text 