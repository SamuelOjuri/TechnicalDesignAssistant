import os
import tempfile
from werkzeug.utils import secure_filename
from flask import current_app
import re

from ..utils.email_extraction import (
    process_eml_file,
    process_msg_file,
    extract_text_from_email
)
from ..utils.pdf_extraction import process_pdf_with_gemini
from ..services.parameter_extraction import extract_parameters, extract_project_name_from_content
from ..utils.llm_interface import query_llm

# Define allowed file extensions
ALLOWED_EXTENSIONS = {'eml', 'msg', 'pdf'}

def allowed_file(filename):
    """Check if the file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_files(files):
    """
    Process uploaded files and extract text and parameters.
    
    Args:
        files: A list of uploaded files
    
    Returns:
        dict: A dictionary containing extracted text, parameters, and project name
    """
    all_text = ""
    email_data = None
    
    for file in files:
        if not file or not allowed_file(file.filename):
            continue
            
        filename = secure_filename(file.filename)
        suffix = f".{filename.split('.')[-1]}"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            file.save(tmp.name)
            path = tmp.name
            
        try:
            if filename.lower().endswith(".eml"):
                header, body, att, inline = process_eml_file(path)
                email_text = header + "\n" + body
                if email_data is None:
                    email_data = {"email_text": email_text, "attachments_data": att}
                extracted = extract_text_from_email(email_text, att, inline)
                all_text += f"\n\nEMAIL FILE: {filename}\n{extracted}\n{'='*50}\n"
            elif filename.lower().endswith(".msg"):
                header, body, att, inline = process_msg_file(path)
                email_text = header + "\n" + body
                if email_data is None:
                    email_data = {"email_text": email_text, "attachments_data": att}
                extracted = extract_text_from_email(email_text, att, inline)
                all_text += f"\n\nOUTLOOK EMAIL FILE: {filename}\n{extracted}\n{'='*50}\n"
            elif filename.lower().endswith(".pdf"):
                pdf_text = process_pdf_with_gemini(file.read(), filename)
                all_text += f"\n\nPDF FILE: {filename}\n{pdf_text}\n{'='*50}\n"
        finally:
            # Clean up the temporary file
            if os.path.exists(path):
                os.remove(path)
    
    # Extract project name if email data is available
    project_name = None
    if email_data:
        project_name = extract_project_name_from_content(
            email_data['email_text'], 
            email_data['attachments_data']
        )
    
    # Extract parameters from the text using LLM
    params = extract_parameters(all_text)
    
    # Set reason for change to "New Enquiry" by default for new uploads
    # if no specific reason was found by the LLM
    if params and "Reason for Change" in params:
        if not params["Reason for Change"] or params["Reason for Change"] == "Not found":
            params["Reason for Change"] = "New Enquiry"
    
    return {
        "extractedText": all_text,
        "params": params,
        "projectName": project_name
    } 