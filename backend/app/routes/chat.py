from flask import Blueprint, request, jsonify, current_app
from ..services.chat_service import generate_chat_response

chat_bp = Blueprint('chat', __name__, url_prefix='/api/chat')

@chat_bp.route('', methods=['POST'])
def chat():
    """
    Generate a response to a chat message based on extracted parameters and text.
    ---
    Args:
        message: The user's message
        params: The extracted parameters (optional)
        extracted_text: The raw extracted text (optional)
    
    Returns:
        JSON with the generated response
    """
    data = request.json
    if not data or 'message' not in data:
        return jsonify({'error': 'No message provided'}), 400
    
    message = data['message']
    params = data.get('params', {})
    extracted_text = data.get('extractedText', '')
    param_sources = data.get('paramSources', {})
    enquiry_type = data.get('enquiryType', None)
    
    # Add debug logging here too
    print(f"Route received extracted_text: {extracted_text[:100]}...")
    
    # Handle special commands
    if message.strip().lower() == "/raw" and extracted_text:
        return jsonify({
            'response': "Raw extracted text:",
            'raw_text': extracted_text
        })
    
    # Generate response from chat service
    response = generate_chat_response(
        message=message,
        params=params,
        extracted_text=extracted_text,
        param_sources=param_sources,
        enquiry_type=enquiry_type
    )
    
    return jsonify({'response': response}) 