import os
from email.parser import BytesParser
from email import policy
import extract_msg
import io
from flask import current_app
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo
from typing import Tuple, Dict, List, Union, BinaryIO
from datetime import datetime
import logging
import time

from .pdf_extraction import process_pdf_with_gemini, process_pdf_batch, should_batch_pdfs
from .image_extraction import process_image_with_gemini
from .thread_pool import process_items_in_parallel

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_email_content(email_content: bytes, filename: str) -> Tuple[str, str, List[Dict], List[Dict]]:
    """
    Process email content directly from bytes without disk I/O.
    
    Args:
        email_content: Raw email content in bytes
        filename: Original filename for type detection
        
    Returns:
        Tuple of (header_info, body, attachments_data, inline_images)
    """
    if filename.lower().endswith('.msg'):
        # For MSG files, we need to use a BytesIO since extract_msg expects a file-like object
        with io.BytesIO(email_content) as bio:
            msg = extract_msg.Message(bio)
            try:
                # Extract date
                raw_date = msg.date or ""
                local_date_str = format_email_date(raw_date)
                
                # Extract header fields
                header_info = (
                    f"From: {msg.sender}\n"
                    f"To: {msg.to}\n"
                    f"Subject: {msg.subject}\n"
                    f"Date: {local_date_str}\n"
                )
                
                body = msg.body
                
                # Process attachments
                attachments_data = []
                inline_images = []
                
                for attachment in msg.attachments:
                    att_filename = attachment.longFilename or attachment.shortFilename
                    if att_filename:
                        is_inline = is_inline_attachment(attachment, msg, att_filename)
                        
                        if is_inline:
                            inline_images.append({
                                'filename': att_filename,
                                'content': attachment.data,
                                'content_id': getattr(attachment, 'cid', None),
                                'mime_type': f"image/{att_filename.split('.')[-1].lower()}"
                            })
                        else:
                            attachments_data.append({
                                'filename': att_filename,
                                'content': attachment.data
                            })
            finally:
                msg.close()
    else:
        # For EML files, use email.parser
        msg = BytesParser(policy=policy.default).parsebytes(email_content)
        
        # Extract date
        raw_date = msg.get('date', '')
        local_date_str = format_email_date(raw_date)
        
        # Extract header fields
        header_info = (
            f"From: {msg.get('from', '')}\n"
            f"To: {msg.get('to', '')}\n"
            f"Subject: {msg.get('subject', '')}\n"
            f"Date: {local_date_str}\n"
        )
        
        # Extract body
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain" and not part.get_filename():
                    body += part.get_content() + "\n"
        else:
            body = msg.get_content()
        
        # Process attachments
        attachments_data = []
        inline_images = []
        
        for part in msg.iter_attachments():
            att_filename = part.get_filename()
            if att_filename:
                content = part.get_payload(decode=True)
                if is_inline_image(part, att_filename):
                    inline_images.append({
                        'filename': att_filename,
                        'content': content,
                        'content_id': part.get('Content-ID'),
                        'mime_type': part.get_content_type()
                    })
                else:
                    attachments_data.append({
                        'filename': att_filename,
                        'content': content
                    })
    
    return header_info, body, attachments_data, inline_images

def format_email_date(raw_date: Union[str, datetime]) -> str:
    """Format email date to local time string."""
    if not raw_date:
        return raw_date
    
    try:
        if isinstance(raw_date, str):
            dt = parsedate_to_datetime(raw_date)
        else:
            dt = raw_date
        
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        
        dt_local = dt.astimezone(ZoneInfo("Europe/London"))
        return dt_local.strftime("%a, %d %b %Y %H:%M:%S %z")
    except Exception as e:
        print(f"Date parsing error: {e}")
        return str(raw_date)

def is_inline_image(part, filename: str) -> bool:
    """Check if an email part is an inline image."""
    return (
        filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')) and
        bool(part.get('Content-ID'))
    )

def is_inline_attachment(attachment, msg, filename: str) -> bool:
    """Check if an MSG attachment is an inline image."""
    return (
        filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')) and
        (
            (hasattr(attachment, 'cid') and attachment.cid) or
            (hasattr(msg, 'htmlBody') and msg.htmlBody and 
             filename in msg.htmlBody.decode('utf-8', errors='ignore'))
        )
    )

def extract_text_from_email(email_text: str, attachments_data: List[Dict], inline_images: List[Dict] = None) -> str:
    """Extract text from email and process attachments in parallel."""
    logger.info("Starting email attachment processing")
    start_time = time.time()
    
    combined_text = f"EMAIL CONTENT:\n{email_text}\n\n"
    
    # Prepare visual items for processing
    visual_items = []
    
    # Sort PDFs by size (process smaller files first)
    pdf_attachments = sorted(
        [att for att in attachments_data if att['filename'].lower().endswith('.pdf')],
        key=lambda x: len(x['content'])
    )
    
    # Decide once whether they can be submitted together
    if pdf_attachments and should_batch_pdfs(pdf_attachments):
        visual_items.append(('pdf_batch', pdf_attachments))
        logger.info(f"Added PDF batch with {len(pdf_attachments)} files")
    else:
        visual_items.extend(('pdf', pdf) for pdf in pdf_attachments)
        logger.info(f"Added {len(pdf_attachments)} individual PDFs")
    
    # Add image attachments
    image_attachments = [
        att for att in attachments_data
        if any(att['filename'].lower().endswith(ext) 
               for ext in ('.jpg', '.jpeg', '.png', '.gif', '.bmp'))
    ]
    visual_items.extend(('image', img) for img in image_attachments)
    
    # Add inline images
    if inline_images:
        visual_items.extend(('inline', img) for img in inline_images)
    
    logger.info(f"Found {len(visual_items)} visual items to process")
    
    # Process non-visual attachments
    non_visual = [
        att for att in attachments_data 
        if not any(att['filename'].lower().endswith(ext) 
                  for ext in ('.pdf', '.jpg', '.jpeg', '.png', '.gif', '.bmp'))
    ]
    for attachment in non_visual:
        combined_text += f"\nATTACHMENT ({attachment['filename']}) [Not processed - not a PDF or image]\n\n"
    
    # Conservative parallel processing to avoid rate limits
    MAX_WORKERS = 7  # Optimal based on performance testing
    # Remove BATCH_SIZE logic - let MAX_WORKERS and rate limiter handle concurrency
    BATCH_SIZE = None  # Always process all items concurrently (limited by MAX_WORKERS)
    
    logger.info(f"Processing with MAX_WORKERS={MAX_WORKERS}, BATCH_SIZE={BATCH_SIZE}")
    
    # Get app context
    app = current_app._get_current_object()
    
    def _process_visual(item_type: str, item: Union[Dict, List[Dict]]) -> Tuple[str, str]:
        """Process a single visual item or batch."""
        item_start = time.time()
        
        try:
            if item_type == 'pdf_batch':
                total_size = sum(len(pdf['content']) for pdf in item) / (1024 * 1024)
                logger.info(f"Processing PDF batch with {len(item)} files ({total_size:.2f}MB total)")
                text = process_pdf_batch(item)  # item is the list of PDFs
                header = "\nBATCHED PDF ATTACHMENTS:\n"
                logger.info(f"Processed PDF batch in {time.time() - item_start:.2f}s")
                return "batched_pdfs", f"{header}{text}\n\n"
            elif item_type == 'pdf':
                file_size = len(item['content']) / (1024 * 1024)  # Size in MB
                logger.info(f"Starting to process {item['filename']} ({file_size:.2f}MB)")
                text = process_pdf_with_gemini(item['content'], item['filename'])
                logger.info(f"Processed PDF {item['filename']} in {time.time() - item_start:.2f}s")
                return item['filename'], f"\nPDF ATTACHMENT ({item['filename']}):\n{text}\n\n"
            elif item_type == 'inline':
                file_size = len(item['content']) / (1024 * 1024)  # Size in MB
                logger.info(f"Starting to process {item['filename']} ({file_size:.2f}MB)")
                text = process_image_with_gemini(item['content'], item['filename'], "INLINE IMAGE")
                logger.info(f"Processed inline image {item['filename']} in {time.time() - item_start:.2f}s")
                return item['filename'], f"\nINLINE IMAGE ({item['filename']}):\n{text}\n\n"
            else:  # image attachment
                file_size = len(item['content']) / (1024 * 1024)  # Size in MB
                logger.info(f"Starting to process {item['filename']} ({file_size:.2f}MB)")
                text = process_image_with_gemini(item['content'], item['filename'], "ATTACHMENT")
                logger.info(f"Processed image {item['filename']} in {time.time() - item_start:.2f}s")
                return item['filename'], f"\nIMAGE ATTACHMENT ({item['filename']}):\n{text}\n\n"
        except Exception as e:
            if item_type == 'pdf_batch':
                logger.error(f"Error processing PDF batch: {str(e)}")
                return "batched_pdfs", f"\nError processing PDF batch: {str(e)}\n\n"
            else:
                logger.error(f"Error processing {item['filename']}: {str(e)}")
                return item['filename'], f"\nError processing {item_type.upper()} ({item['filename']}): {str(e)}\n\n"
    
    # Process items in parallel
    results = process_items_in_parallel(
        visual_items,
        _process_visual,
        max_workers=MAX_WORKERS,
        batch_size=BATCH_SIZE
    )
    
    # Maintain original order (with special handling for batched PDFs)
    order_map = {}
    for idx, item in enumerate(visual_items):
        if item[0] == 'pdf_batch':
            order_map["batched_pdfs"] = idx
        else:
            order_map[item[1]['filename']] = idx
    
    sorted_results = sorted(results, key=lambda x: order_map.get(x[0], float('inf')))
    
    # Add results to combined text
    for _, text in sorted_results:
        combined_text += text
    
    logger.info(f"Completed email attachment processing in {time.time() - start_time:.2f}s")
    return combined_text

def process_eml_file(eml_file_path):
    """
    Legacy function maintained for compatibility.
    Processes a single .eml file from disk.
    """
    with open(eml_file_path, 'rb') as f:
        content = f.read()
    return process_email_content(content, eml_file_path)

def process_msg_file(msg_file_path):
    """
    Legacy function maintained for compatibility.
    Processes a single .msg file from disk.
    """
    with open(msg_file_path, 'rb') as f:
        content = f.read()
    return process_email_content(content, msg_file_path) 