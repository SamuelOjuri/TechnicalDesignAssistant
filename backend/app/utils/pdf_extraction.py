import os
import tempfile
from flask import current_app
from google.genai import types
from .llm_interface import gemini_api_with_retry

def process_pdf_with_gemini(pdf_content, filename):
    """
    Process PDF content using Gemini's File API.
    
    Args:
        pdf_content: The binary content of the PDF file
        filename: Name of the PDF file
    
    Returns:
        str: Extracted text from the PDF
    """
    try:
        # Create a temporary file to use with Gemini
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_file.write(pdf_content)
            temp_file_path = temp_file.name
        
        # Create a prompt to extract text and information from the PDF
        prompt = "Please extract all text content from this PDF document, including text from tables, diagrams, and charts."
        
        # Process the PDF with Gemini using the client approach
        with open(temp_file_path, 'rb') as f:
            pdf_data = f.read()
            
            # Use retry function instead of direct API call
            model = current_app.config.get('GEMINI_MODEL', "gemini-2.5-flash-preview-04-17")
            response = gemini_api_with_retry(
                model=model,
                contents=[
                    types.Part.from_bytes(
                        data=pdf_data,
                        mime_type='application/pdf',
                    ),
                    prompt
                ]
            )
            
        return response.text
    except Exception as e:
        print(f"Error processing PDF with Gemini: {e}")
        return f"Error processing PDF: {str(e)}"
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

def process_multiple_pdfs(pdf_files):
    """
    Process multiple PDF files with Gemini.
    
    Args:
        pdf_files: List of PDF file data (content and filename)
        
    Returns:
        combined_text: Combined text from all PDFs
    """
    combined_text = ""
    
    for pdf_file in pdf_files:
        filename = pdf_file['filename']
        content = pdf_file['content']
        
        # Process each PDF and append its text
        pdf_text = process_pdf_with_gemini(content, filename)
        combined_text += f"\nPDF ATTACHMENT ({filename}):\n{pdf_text}\n\n"
    
    return combined_text 