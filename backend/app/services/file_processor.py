import os
import tempfile
from werkzeug.utils import secure_filename
from flask import current_app
import re
from typing import List, Dict, Any
import logging
import time

from ..utils.email_extraction import (
    process_email_content,
    extract_text_from_email
)
from ..utils.pdf_extraction import process_pdf_batch
from ..services.parameter_extraction import extract_parameters, extract_project_name_from_content

# Define allowed file extensions
ALLOWED_EXTENSIONS = {'eml', 'msg', 'pdf'}

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def allowed_file(filename):
    """Check if the file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_files(files: List[Any]) -> Dict:
    """
    Process uploaded files with optimized parallel processing and batching.
    
    Args:
        files: List of uploaded files
        
    Returns:
        Dict containing extracted text, parameters, and project name
    """
    logger.info(f"Starting to process {len(files)} files")
    start_time = time.time()
    
    all_text = ""
    email_data = None
       
    # Separate PDFs and emails
    pdf_files = []
    email_files = []
    
    for file in files:
        if not file or not allowed_file(file.filename):
            continue
        
        filename = secure_filename(file.filename)
        content = file.read()  # Read content once
        
        if filename.lower().endswith('.pdf'):
            pdf_files.append({
                'filename': filename,
                'content': content
            })
        else:  # .eml or .msg
            email_files.append({
                'filename': filename,
                'content': content
            })
    
    logger.info(f"Found {len(pdf_files)} PDFs and {len(email_files)} emails")
    
    # Process PDFs in optimized batches
    if pdf_files:
        pdf_start = time.time()
        BATCH_SIZE = 5
        for i in range(0, len(pdf_files), BATCH_SIZE):
            batch = pdf_files[i:i + BATCH_SIZE]
            logger.info(f"Processing PDF batch {i//BATCH_SIZE + 1} of {(len(pdf_files) + BATCH_SIZE - 1)//BATCH_SIZE}")
            batch_text = process_pdf_batch(batch)
            all_text += f"\n{batch_text}\n{'='*50}\n"
        logger.info(f"Completed PDF processing in {time.time() - pdf_start:.2f}s")
    
    # Process emails
    for email_file in email_files:
        try:
            # Process email content directly from bytes
            header, body, attachments, inline_images = process_email_content(
                email_file['content'],
                email_file['filename']
            )
            
            email_text = f"{header}\n{body}"
            
            # Store first email's data for project name extraction
            if email_data is None:
                email_data = {
                    'email_text': email_text,
                    'attachments_data': attachments
                }
            
            # Process email content and attachments
            extracted = extract_text_from_email(email_text, attachments, inline_images)
            all_text += f"\n\nEMAIL FILE: {email_file['filename']}\n{extracted}\n{'='*50}\n"
            
        except Exception as e:
            print(f"Error processing email {email_file['filename']}: {str(e)}")
            all_text += f"\n\nError processing email {email_file['filename']}: {str(e)}\n{'='*50}\n"
    
    # Extract parameters and project name
    params = extract_parameters(all_text)
    
    project_name = None
    if email_data:
        project_name = extract_project_name_from_content(
            email_data['email_text'],
            all_text
        )
    
    # Set default reason for change
    if params and "Reason for Change" in params:
        if not params["Reason for Change"] or params["Reason for Change"] == "Not found":
            params["Reason for Change"] = "New Enquiry"
    
    logger.info(f"Completed all processing in {time.time() - start_time:.2f}s")
    
    return {
        "extractedText": all_text,
        "params": params,
        "projectName": project_name
    } 