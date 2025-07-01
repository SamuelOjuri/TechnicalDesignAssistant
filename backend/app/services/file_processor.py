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
    
    # Get Flask app instance
    app = current_app._get_current_object()
    
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
    
    # Process ALL PDFs in parallel (no sequential batching)
    if pdf_files:
        pdf_start = time.time()
        logger.info(f"Processing all {len(pdf_files)} PDFs in parallel")
        all_pdfs_text = process_pdf_batch(pdf_files)  # Process all at once
        all_text += f"\n{all_pdfs_text}\n{'='*50}\n"
        logger.info(f"Completed PDF processing in {time.time() - pdf_start:.2f}s")
    
    # Process emails in parallel using thread pool
    if email_files:
        email_start = time.time()
        logger.info(f"Processing {len(email_files)} emails in parallel")
        
        def process_single_email(email_file):
            try:
                header, body, attachments, inline_images = process_email_content(
                    email_file['content'],
                    email_file['filename']
                )
                
                email_text = f"{header}\n{body}"
                extracted = extract_text_from_email(email_text, attachments, inline_images)
                
                return {
                    'filename': email_file['filename'],
                    'text': f"\n\nEMAIL FILE: {email_file['filename']}\n{extracted}\n{'='*50}\n",
                    'email_data': {
                        'email_text': email_text,
                        'attachments_data': attachments
                    }
                }
            except Exception as e:
                logger.error(f"Error processing email {email_file['filename']}: {str(e)}")
                return {
                    'filename': email_file['filename'],
                    'text': f"\n\nError processing email {email_file['filename']}: {str(e)}\n{'='*50}\n",
                    'email_data': None
                }
        
        # Replace custom ThreadPoolExecutor with context-aware thread pool
        from ..utils.thread_pool import process_items_in_parallel
        
        # Convert email_files to the format expected by process_items_in_parallel
        email_items = [('email', email_file) for email_file in email_files]
        
        # Process using context-aware thread pool
        results = process_items_in_parallel(
            email_items,
            lambda item_type, email_file: (
                email_file['filename'],
                process_single_email(email_file)
            ),
            max_workers=min(12, len(email_files))
        )
        
        # Process results
        for filename, result in results:
            all_text += result['text']
            
            # Store first email's data for project name extraction
            if email_data is None and result['email_data']:
                email_data = result['email_data']
        
        logger.info(f"Completed email processing in {time.time() - email_start:.2f}s")
    
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