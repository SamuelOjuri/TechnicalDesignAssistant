import os
from email.parser import BytesParser
from email import policy
import extract_msg
from flask import current_app
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo   # Py-3.9+; use pytz if you're on ≤3.8

from .pdf_extraction import process_pdf_with_gemini
from .image_extraction import process_image_with_gemini

def process_eml_file(eml_file_path):
    """
    Processes a single .eml file:
      - Parses the email to extract header and body.
      - Extracts attachments and inline images and returns their data.
    
    Returns:
      header: string with key header fields.
      body: string containing the plain text body.
      attachments_data: list of dictionaries with attachment data.
      inline_images: list of dictionaries with inline image data.
    """
    # Open and parse the email file using the default email policy
    with open(eml_file_path, 'rb') as f:
        msg = BytesParser(policy=policy.default).parse(f)

    # Parse and local-ise the date
    raw_date = msg.get('date', '')
    local_date_str = raw_date            # fallback if parsing fails
    if raw_date:
        try:
            dt = parsedate_to_datetime(raw_date)   # returns aware dt if hdr has TZ
            if dt.tzinfo is None:                  # safety – treat naïve as UTC
                dt = dt.replace(tzinfo=ZoneInfo("UTC"))
            dt_local = dt.astimezone(ZoneInfo("Europe/London"))
            local_date_str = dt_local.strftime("%a, %d %b %Y %H:%M:%S %z")
        except Exception:
            pass  # keep original string on failure

    # Extract header fields
    header_info = (
        f"From: {msg.get('from', '')}\n"
        f"To: {msg.get('to', '')}\n"
        f"Subject: {msg.get('subject', '')}\n"
        f"Date: {local_date_str}\n"
    )
    
    # Extract the email body
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                body += part.get_content() + "\n"
    else:
        body = msg.get_content()
    
    # Process attachments and inline images
    attachments_data = []
    inline_images = []
    
    for part in msg.iter_attachments():
        filename = part.get_filename()
        if filename:
            # Check if this is an inline image
            is_inline = False
            content_id = part.get('Content-ID')
            
            # Images with Content-ID are typically inline
            if content_id and filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                is_inline = True
                
            if is_inline:
                inline_image_data = {
                    'filename': filename,
                    'content': part.get_payload(decode=True),
                    'content_id': content_id,
                    'mime_type': part.get_content_type()
                }
                inline_images.append(inline_image_data)
            else:
                attachment_data = {
                    'filename': filename,
                    'content': part.get_payload(decode=True)
                }
                attachments_data.append(attachment_data)
    
    return header_info, body, attachments_data, inline_images

def process_msg_file(msg_file_path):
    """
    Processes a single .msg file (Outlook email format):
      - Parses the email to extract header and body.
      - Extracts attachments and inline images and returns their data.
    
    Returns:
      header: string with key header fields.
      body: string containing the plain text body.
      attachments_data: list of dictionaries with attachment data.
      inline_images: list of dictionaries with inline image data.
    """
    # Open and parse the Outlook message file
    msg = extract_msg.Message(msg_file_path)
    
    try:
        # ---------------------------------------------------------
        # Convert the Outlook MSG date to UK local time (BST/GMT)
        # ---------------------------------------------------------
        raw_date = msg.date or ""
        local_date_str = raw_date                 # fallback
        if raw_date:
            try:
                # Handle different date formats from extract_msg
                if isinstance(raw_date, str):
                    # If it's a string, try to parse with parsedate_to_datetime
                    dt = parsedate_to_datetime(raw_date)
                else:
                    # If it's already a datetime object, use it directly
                    dt = raw_date
                
                # Ensure timezone awareness
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=ZoneInfo("UTC"))
                
                # Convert to UK local time
                dt_local = dt.astimezone(ZoneInfo("Europe/London"))
                local_date_str = dt_local.strftime("%a, %d %b %Y %H:%M:%S %z")
                
                # Debug logging for server troubleshooting
                print(f"MSG Date Debug - Raw: {raw_date} (type: {type(raw_date)})")
                print(f"MSG Date Debug - Parsed: {dt}")
                print(f"MSG Date Debug - Local: {dt_local}")
                print(f"MSG Date Debug - Formatted: {local_date_str}")
                
            except Exception as e:
                print(f"MSG Date parsing error: {e}")
                pass  # keep the original string on failure

        # Extract header fields
        header_info = (
            f"From: {msg.sender}\n"
            f"To: {msg.to}\n"
            f"Subject: {msg.subject}\n"
            f"Date: {local_date_str}\n"
        )
        
        # Extract the email body
        body = msg.body
        
        # Process attachments and inline images
        attachments_data = []
        inline_images = []
        
        for attachment in msg.attachments:
            filename = attachment.longFilename or attachment.shortFilename
            if filename:
                # Try to determine if it's an inline image
                is_inline = False
                
                # Look for typical image extensions and check if it might be inline
                # Outlook msg format doesn't clearly distinguish inline vs attachment 
                # so we'll use heuristics
                if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                    # Check if there's a content ID or if it's referenced in HTML
                    # This is a heuristic approach
                    if hasattr(attachment, 'cid') and attachment.cid:
                        is_inline = True
                    elif hasattr(msg, 'htmlBody') and msg.htmlBody and filename in msg.htmlBody.decode('utf-8', errors='ignore'):
                        is_inline = True
                        
                if is_inline:
                    inline_image_data = {
                        'filename': filename,
                        'content': attachment.data,
                        'content_id': attachment.cid if hasattr(attachment, 'cid') else None,
                        'mime_type': f"image/{filename.split('.')[-1].lower()}"
                    }
                    inline_images.append(inline_image_data)
                else:
                    attachment_data = {
                        'filename': filename,
                        'content': attachment.data
                    }
                    attachments_data.append(attachment_data)
        
        return header_info, body, attachments_data, inline_images
    
    finally:
        # Close the msg file to release the file handle
        msg.close()

def extract_text_from_email(email_text, attachments_data, inline_images=None):
    """Extracts all text from email and attachments returns as a single string."""
    combined_text = f"EMAIL CONTENT:\n{email_text}\n\n"
    
    # For non-visual content attachments, just note they exist
    for attachment in attachments_data:
        filename = attachment['filename']
        if not (filename.lower().endswith(".pdf") or 
                filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp'))):
            combined_text += f"\nATTACHMENT ({filename}) [Not processed - not a PDF or image]\n\n"
    
    # Limit the total number of visual items to process to avoid rate limits
    MAX_VISUAL_ITEMS = 10
    
    # Collect all visual attachments
    pdf_attachments = [a for a in attachments_data if a['filename'].lower().endswith(".pdf")]
    image_attachments = [a for a in attachments_data if a['filename'].lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp'))]
    
    all_visual_items = []
    
    # Add most important items first
    if pdf_attachments:
        all_visual_items.extend([('pdf', pdf) for pdf in pdf_attachments])
    if image_attachments:
        all_visual_items.extend([('image', img) for img in image_attachments])
    if inline_images:
        all_visual_items.extend([('inline', img) for img in inline_images])
    
    # Process only a limited number of items
    processed_items = all_visual_items[:MAX_VISUAL_ITEMS]
    skipped_items = all_visual_items[MAX_VISUAL_ITEMS:]
    
    # Note skipped items
    if skipped_items:
        combined_text += "\nNOTE: Some visual elements were not processed due to API rate limits:\n"
        for item_type, item in skipped_items:
            combined_text += f"- {item_type.upper()}: {item['filename']}\n"
        combined_text += "\n"
    
    # Process the limited set of items
    for item_type, item in processed_items:
        if item_type == 'pdf':
            # Process this PDF
            pdf_text = process_pdf_with_gemini(item['content'], item['filename'])
            combined_text += f"\nPDF ATTACHMENT ({item['filename']}):\n{pdf_text}\n\n"
        elif item_type == 'inline':
            # Process this inline image
            image_text = process_image_with_gemini(item['content'], item['filename'], "INLINE IMAGE")
            combined_text += f"\nINLINE IMAGE ({item['filename']}):\n{image_text}\n\n"
        elif item_type == 'image':
            # Process this image attachment
            image_text = process_image_with_gemini(item['content'], item['filename'], "ATTACHMENT")
            combined_text += f"\nIMAGE ATTACHMENT ({item['filename']}):\n{image_text}\n\n"
    
    return combined_text 