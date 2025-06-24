import time
import logging
import base64
from typing import List, Dict, Any
from celery import current_task
from flask import current_app
from werkzeug.utils import secure_filename
from ..celery_app import create_celery_app
from ..services.file_processor import process_files as sync_process_files, allowed_file
from ..utils.progress_tracker import ProgressTracker
from ..utils.pdf_extraction import process_pdf_batch
from ..utils.email_extraction import process_email_content, extract_text_from_email
from ..services.parameter_extraction import extract_parameters, extract_project_name_from_content

# Set up logging
logger = logging.getLogger(__name__)

# Create Celery instance
celery = create_celery_app()

@celery.task(bind=True, track_started=True)
def process_files_async(self, files_data: List[Dict[str, Any]], job_id: str):
    """
    Asynchronously process uploaded files with progress tracking.
    
    Args:
        files_data: List of file data dictionaries with 'filename', 'content', etc.
        job_id: Unique job identifier for progress tracking
    
    Returns:
        Dict containing extracted text, parameters, and project name
    """
    progress_tracker = ProgressTracker(job_id)
    
    try:
        # Update progress: Starting
        progress_tracker.update_progress(
            stage="initializing",
            current_file="",
            progress=0,
            message="Initializing file processing..."
        )
        
        # Simulate file objects for existing process_files function
        class FileWrapper:
            def __init__(self, filename, content):
                self.filename = filename
                self._content = content
                self._position = 0
            
            def read(self, size=-1):
                if self._position == 0:
                    self._position = len(self._content)
                    return self._content
                return b''
        
        files = [FileWrapper(f['filename'], base64.b64decode(f['content'])) for f in files_data]
        
        # Update progress: Processing started
        progress_tracker.update_progress(
            stage="processing",
            current_file="",
            progress=10,
            message=f"Starting to process {len(files)} files..."
        )
        
        # Process files with progress callbacks
        result = process_files_with_progress(files, progress_tracker)
        
        # Update progress: Completed
        progress_tracker.update_progress(
            stage="completed",
            current_file="",
            progress=100,
            message="Processing completed! Results are ready."
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error in async file processing: {str(e)}")
        progress_tracker.update_progress(
            stage="error",
            current_file="",
            progress=0,
            message=f"Error processing files: {str(e)}",
            error=str(e)
        )
        raise

def process_files_with_progress(files: List[Any], progress_tracker: ProgressTracker) -> Dict:
    """
    Modified version of process_files that reports progress.
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
        content = file.read()
        
        if filename.lower().endswith('.pdf'):
            pdf_files.append({
                'filename': filename,
                'content': content
            })
        else:
            email_files.append({
                'filename': filename,
                'content': content
            })
    
    total_files = len(pdf_files) + len(email_files)
    processed_count = 0
    
    # Process PDFs
    if pdf_files:
        for i, pdf_file in enumerate(pdf_files):
            progress_tracker.update_progress(
                stage="processing_pdfs",
                current_file=pdf_file['filename'],
                progress=int(20 + (processed_count / total_files) * 60),
                message=f"Processing PDF: {pdf_file['filename']}"
            )
            
            # Process individual PDF (you can modify this to use your batch logic)
            batch_text = process_pdf_batch([pdf_file])
            all_text += f"\n{batch_text}\n{'='*50}\n"
            
            processed_count += 1
            
            # Stream partial result
            progress_tracker.stream_partial_result(
                f"PDF_PROCESSED:{pdf_file['filename']}",
                f"Successfully processed {pdf_file['filename']}"
            )
    
    # Process emails
    for i, email_file in enumerate(email_files):
        progress_tracker.update_progress(
            stage="processing_emails",
            current_file=email_file['filename'],
            progress=int(20 + (processed_count / total_files) * 60),
            message=f"Processing email: {email_file['filename']}"
        )
        
        try:
            # Process email (using your existing logic)
            header, body, attachments, inline_images = process_email_content(
                email_file['content'],
                email_file['filename']
            )
            
            email_text = f"{header}\n{body}"
            
            if email_data is None:
                email_data = {
                    'email_text': email_text,
                    'attachments_data': attachments
                }
            
            extracted = extract_text_from_email(email_text, attachments, inline_images)
            all_text += f"\n\nEMAIL FILE: {email_file['filename']}\n{extracted}\n{'='*50}\n"
            
            processed_count += 1
            
            # Stream partial result
            progress_tracker.stream_partial_result(
                f"EMAIL_PROCESSED:{email_file['filename']}",
                f"Successfully processed {email_file['filename']}"
            )
            
        except Exception as e:
            logger.error(f"Error processing email {email_file['filename']}: {str(e)}")
            progress_tracker.stream_partial_result(
                f"EMAIL_ERROR:{email_file['filename']}",
                f"Error processing {email_file['filename']}: {str(e)}"
            )
            all_text += f"\n\nError processing email {email_file['filename']}: {str(e)}\n{'='*50}\n"
    
    # Extract parameters
    progress_tracker.update_progress(
        stage="extracting_parameters",
        current_file="",
        progress=85,
        message="Extracting parameters from processed content..."
    )
    
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
    
    progress_tracker.update_progress(
        stage="finalizing",
        current_file="",
        progress=95,
        message="Finalizing results..."
    )
    
    logger.info(f"Completed all processing in {time.time() - start_time:.2f}s")
    
    return {
        "extractedText": all_text,
        "params": params,
        "projectName": project_name
    }
