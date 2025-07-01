import os
import tempfile
from flask import current_app
from google.genai import types
from .llm_interface import gemini_api_with_retry

def process_image_with_gemini(image_content, filename, image_type="ATTACHMENT"):
    """
    Process a single image with Gemini.
    
    Args:
        image_content: The binary content of the image file
        filename: Name of the image file
        image_type: Type of image (ATTACHMENT or INLINE IMAGE)
    
    Returns:
        str: Extracted text and description from the image
    """
    # Define supported image formats and their MIME types
    SUPPORTED_FORMATS = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'webp': 'image/webp'
    }
    
    file_extension = filename.split(".")[-1].lower()
    
    # Validate file format
    if file_extension not in SUPPORTED_FORMATS:
        return f"Unsupported image format: {file_extension}. Only {', '.join(SUPPORTED_FORMATS.keys())} are supported."
    
    # Get proper MIME type
    mime_type = SUPPORTED_FORMATS[file_extension]
    
    try:
        # Process directly from memory - no temp file needed!
        model = current_app.config.get('GEMINI_MODEL', "gemini-2.5-flash")
        response = gemini_api_with_retry(
            model=model,
            contents=[
                types.Part.from_bytes(
                    data=image_content,  # Use image_content directly
                    mime_type=mime_type,
                ),
                "Describe this image in detail, including any visible text, diagrams, or drawings. Extract any technical parameters or specifications you can see."
            ]
        )
        
        return response.text
        
    except Exception as e:
        error_message = str(e)
        # Check if it's specifically a format issue
        if "INVALID_ARGUMENT" in error_message:
            return f"Unable to process this image due to format compatibility issues. Please note any visible information from the image might not be included in the analysis."
        else:
            print(f"Error processing image {filename} with Gemini: {e}")
            return f"Error processing image: {str(e)}"

def process_multiple_images(image_files, image_type="ATTACHMENT"):
    """
    Process multiple image files with Gemini.
    
    Args:
        image_files: List of image file data (content and filename)
        image_type: Type of image (ATTACHMENT or INLINE IMAGE)
        
    Returns:
        combined_text: Combined text from image analysis
    """
    combined_text = ""
    
    for image_file in image_files:
        filename = image_file['filename']
        content = image_file['content']
        
        # Process each image and append its description
        image_text = process_image_with_gemini(content, filename, image_type)
        combined_text += f"\n{image_type} ({filename}):\n{image_text}\n\n"
    
    return combined_text 