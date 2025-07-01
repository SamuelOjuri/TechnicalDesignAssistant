import os
from flask import current_app
from google.genai import types
from .llm_interface import gemini_api_with_retry
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple
import logging
import time
import random

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def should_batch_pdfs(pdf_files: List[Dict]) -> bool:
    """
    Determine if PDFs should be processed in batch based on total size.
    
    Args:
        pdf_files: List of dictionaries containing PDF content
        
    Returns:
        bool: True if PDFs should be batched, False if they should be processed individually
    """
    # More permissive limits to enable batching
    MAX_BATCH_SIZE = 100 * 1024 * 1024  # 100MB (increased from 50MB)
    MAX_FILES_PER_BATCH = 3
    
    total_size = sum(len(f['content']) for f in pdf_files)
    logger.info(f"PDF batch check: {len(pdf_files)} files, {total_size/1024/1024:.2f}MB total")
    
    should_batch = (
        total_size <= MAX_BATCH_SIZE and 
        len(pdf_files) <= MAX_FILES_PER_BATCH and
        len(pdf_files) > 1  # Only batch if we have multiple files
    )
    
    logger.info(f"PDF batching decision: {'BATCH' if should_batch else 'INDIVIDUAL'}")
    return should_batch

def process_pdf_with_gemini(pdf_content: bytes, filename: str) -> str:
    """
    Process PDF content directly with Gemini without writing to disk.
    
    Args:
        pdf_content: Raw bytes of the PDF file
        filename: Name of the PDF file
    
    Returns:
        str: Extracted text from the PDF
    """
    prompt = ("Please extract all text content from this PDF document, "
             "including text from tables, diagrams, and charts.")

    # Use more efficient model for individual PDFs
    model = current_app.config.get('GEMINI_MODEL', "gemini-2.5-flash")
    response = gemini_api_with_retry(
        model=model,
        contents=[
            types.Part.from_bytes(data=pdf_content, mime_type='application/pdf'),
            prompt
        ]
    )
    return response.text

def process_multiple_pdfs_single_call(pdf_files: List[Dict]) -> str:
    """
    Process multiple PDFs in a single Gemini API call.
    
    Args:
        pdf_files: List of dicts with 'content' and 'filename' keys
        
    Returns:
        str: Combined extracted text from all PDFs
    """
    logger.info(f"Processing {len(pdf_files)} PDFs in single batch call")
    
    parts = []
    for f in pdf_files:
        parts.append(types.Part.from_bytes(data=f['content'], mime_type='application/pdf'))
    
    # Add instruction prompt with filenames for better organization
    filenames = ", ".join(f['filename'] for f in pdf_files)
    parts.append(
        f"Please extract all text content from these {len(pdf_files)} PDF documents: {filenames}. "
        "Including text from tables, diagrams, and charts. "
        "For each document, start with '=== PDF: [filename] ===' header and then provide the extracted content."
    )
    
    # Use more efficient model for batch processing
    model = current_app.config.get('GEMINI_MODEL', "gemini-2.5-flash")
    response = gemini_api_with_retry(model=model, contents=parts)
    return response.text

def process_pdfs_in_parallel(pdf_files: List[Dict]) -> str:
    """Process PDFs in parallel using thread pool with rate limiting."""
    logger.info(f"Starting parallel processing of {len(pdf_files)} PDFs")
    start_time = time.time()
    
    def _process_single_pdf(pdf_file: Dict) -> Tuple[str, str]:
        pdf_start = time.time()
        
        text = process_pdf_with_gemini(pdf_file['content'], pdf_file['filename'])
        logger.info(f"Processed {pdf_file['filename']} in {time.time() - pdf_start:.2f}s")
        return pdf_file['filename'], text
    
    results = []
    # Increase max_workers for better performance on upgraded infrastructure
    with ThreadPoolExecutor(max_workers=12) as ex:  # Increased from 5 to 12
        futures = {ex.submit(_process_single_pdf, pdf): pdf for pdf in pdf_files}
        for f in as_completed(futures):
            try:
                filename, text = f.result()
                results.append((
                    filename,
                    f"=== PDF: {filename} ===\n{text}\n"
                ))
            except Exception as e:
                pdf = futures[f]
                logger.error(f"Error processing {pdf['filename']}: {str(e)}")
                results.append((
                    pdf['filename'],
                    f"Error processing PDF: {str(e)}"
                ))
    
    logger.info(f"Completed parallel processing in {time.time() - start_time:.2f}s")
    
    # Combine results in original order
    return "\n".join(text for _, text in sorted(
        results,
        key=lambda x: pdf_files.index(next(p for p in pdf_files if p['filename'] == x[0]))
    ))

def process_pdf_batch(pdf_files: List[Dict]) -> str:
    """Process a batch of PDFs with intelligent batching decision."""
    if not pdf_files:
        return ""
    
    total_size = sum(len(f['content']) for f in pdf_files)
    logger.info(f"Processing batch of {len(pdf_files)} PDFs (total size: {total_size/1024/1024:.2f}MB)")
    
    if should_batch_pdfs(pdf_files):
        logger.info("Using batch processing for PDFs")
        try:
            return process_multiple_pdfs_single_call(pdf_files)
        except Exception as e:
            logger.error(f"Batch processing failed: {str(e)}, falling back to parallel")
            return process_pdfs_in_parallel(pdf_files)
    else:
        logger.info("Using parallel processing for PDFs")
        return process_pdfs_in_parallel(pdf_files) 