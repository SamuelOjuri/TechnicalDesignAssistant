from flask import current_app
from ..utils.llm_interface import gemini_api_with_retry

def generate_chat_response(message, params=None, extracted_text=None, param_sources=None, enquiry_type=None):
    """
    Generate a response to a chat message based on the extracted parameters and text.
    
    Args:
        message: The user's message
        params: The extracted parameters dictionary
        extracted_text: The raw extracted text
        param_sources: Dictionary mapping parameters to their sources
        enquiry_type: Either "New Enquiry" or "Amendment"
    
    Returns:
        str: The generated response
    """
    # Debug logging to verify extracted_text is received
    print(f"Received extracted_text: {extracted_text[:100]}...")  # Print first 100 chars

    # If we don't have any parameters, return a message asking to process files first
    if not params:
        return "Please process files first to extract parameters."
    
    # Build enhanced context with source information
    params_with_sources = []
    for k, v in params.items():
        source = param_sources.get(k, "Unknown") if param_sources else "Unknown"
        params_with_sources.append(f"• **{k}**: {v} (Source: {source})")
    
    params_text = "\n".join(params_with_sources)
    raw_text = extracted_text or ""
    
    # Enhanced system prompt
    system = (
        f"You are a highly capable roofing-design assistant for TaperedPlus Ltd. This is a {enquiry_type or 'Unknown'} enquiry. Use the details below when answering:\n\n"
        "EXTRACTED PARAMETERS:\n" + params_text + "\n\n"
        "IMPORTANT CONTEXT:\n"
        "- Parameters marked 'Email Content' were extracted from the uploaded documents\n"
        "- Parameters marked 'Monday CRM' came from the existing project database\n"
        "- Parameters marked 'Business Rule' were set by system rules (e.g., 'To be assigned by TaperedPlus')\n"
        "- For New Enquiries, Drawing Reference and Revision are pending assignment\n\n"
        "RAW EXTRACTED TEXT FROM DOCUMENTS:\n" + raw_text
    )
    
    # Use configured model from app config
    model = current_app.config.get('GEMINI_MODEL', "gemini-2.5-flash-preview-05-20")
    
    # Call Gemini API with retry logic
    response = gemini_api_with_retry(model, [system, message])
    
    return response.text 