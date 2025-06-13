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
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(suffix=f'.{file_extension}', delete=False) as temp_file:
        temp_file.write(image_content)
        temp_file_path = temp_file.name
    
    try:
        # Process the image with Gemini
        with open(temp_file_path, 'rb') as f:
            image_data = f.read()
            
            # Use a try/except block specifically for this API call
            try:
                model = current_app.config.get('GEMINI_MODEL', "gemini-2.5-flash-preview-05-20")
                response = gemini_api_with_retry(
                    model=model,
                    contents=[
                        types.Part.from_bytes(
                            data=image_data,
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
                    raise e  # Re-raise the exception for other types of errors
    
    except Exception as e:
        # Use logging instead of st.error
        print(f"Error processing image {filename} with Gemini: {e}")
        return f"Error processing image: {str(e)}"
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

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