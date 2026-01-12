import re
from flask import current_app
from ..utils.llm_interface import query_llm
from ..utils.helpers import map_tapered_insulation_value

def extract_parameters(all_text, enquiry_type=None):
    """
    Extract parameters from the extracted text using LLM.
    
    Args:
        all_text: The extracted text from files
        enquiry_type: Optional - force "Amendment" or "New Enquiry"
    
    Returns:
        dict: A dictionary of extracted parameters
    """
    # Define the base query template
    query = """Extract the following design parameters from the documents for a TaperedPlus technical drawing request: 
            - Email Subject: (The subject line of the email requesting the service from TaperedPlus).
            - Post Code of Project Location: (Mostly found in the title block of the drawing attached to emails. Ignore the postcode of any company office address or sender/recipient address and use the post code of the project location only, otherwise state 'Not provided').
            - Drawing Reference: (TaperedPlus Reference Number e.g. TP*****_**.** - *. Look for references associated with TaperedPlus specifically. If multiple exist, prioritize the latest one mentioned in the context of the request *to* TaperedPlus).
            - Drawing Title (The Project Name, usually the project location).
            - Revision (Suffix of the drawing reference e.g. **.** - A. If multiple exist, use the one associated with the Drawing Reference identified above).
            - Date Received: (Date the email requesting the service *from TaperedPlus* was sent by the client. In a forwarded email chain, this is the date the email was *sent to TaperedPlus*, NOT the date of the original email further down the chain).
            - Hour Received: (Local time the email was sent *to TaperedPlus*. Use 24-hour format, e.g. 14:23).
            - Company: (Identify the company *directly requesting* technical drawings or services *from TaperedPlus*. In a forwarded email, this is the company of the person *sending the email to TaperedPlus*, NOT the company of the original sender further down the chain. Look for the company directly communicating with TaperedPlus).
            - Contact: (Identify the contact person *directly requesting* the job or drawings *from TaperedPlus*. In a forwarded email, this is the person *sending the email to TaperedPlus*, NOT the original sender further down the chain. Look for the individual directly communicating with TaperedPlus).
            - Reason for Change: ({reason_change_text})
            - Surveyor: (Name of the surveyor if provided).
            - Target U-Value: (The primary target U-Value requested for the main insulation area).
            - Target Min U-Value: (A secondary or minimum target U-Value if specified, often for specific areas like upstands).
            - Fall of Tapered: (The required fall or slope for the tapered insulation).
            - Tapered Insulation: (The type or brand of tapered insulation product requested).
            - Decking: (The type of roof decking material described)."""
    
    # Set the Reason for Change text based on the enquiry_type
    if enquiry_type == "Amendment":
        reason_change_text = "Amendment"
    elif enquiry_type == "New Enquiry":
        reason_change_text = "New Enquiry"
    else:
        reason_change_text = "Either 'Amendment' or 'New Enquiry' depending on the context of the email"
    
    # Format the query with the appropriate Reason for Change text
    formatted_query = query.format(reason_change_text=reason_change_text)
    
    # Send to Gemini for analysis
    resp = query_llm(all_text, formatted_query)
    
    # Parse the response into structured data
    df_row = {}
    for p in [
        "Email Subject", "Post Code", "Drawing Reference", "Drawing Title", "Revision", 
        "Date Received", "Hour Received", "Company", "Contact", "Reason for Change", 
        "Surveyor", "Target U-Value", "Target Min U-Value", 
        "Fall of Tapered", "Tapered Insulation", "Decking"
    ]:
        # Accept both "Key: value" and "Key : value"
        m = re.search(rf"{p}\s*:?\s*(.*?)(?:\n|$)", resp, re.I)
        val = m.group(1).strip() if m else "Not found"
        # Remove leading asterisks from all values
        val = re.sub(r'^\*+\s*', '', val)
        
        # Special processing for specific parameters
        if p == "Tapered Insulation":
            val = map_tapered_insulation_value(val)
        # For Post Code, extract just the postcode area (initial letters)
        elif p == "Post Code":
            # First clean up any formatting from the LLM response
            cleaned_value = re.sub(r'^\s*of Project Location:?\*?\s*', '', val, flags=re.IGNORECASE)
            cleaned_value = cleaned_value.strip()
            
            # Check if the value indicates "not provided" or similar
            if re.search(r'not\s+provided|not\s+found|none', cleaned_value, re.IGNORECASE):
                val = "Not provided"
            else:
                # Define UK postcode pattern
                uk_postcode_pattern = r'([A-Z]{1,2})[0-9]'
                postcode_match = re.search(uk_postcode_pattern, cleaned_value.upper())
                if postcode_match:
                    val = postcode_match.group(1)
                else:
                    # Keep original value if it doesn't match a postcode pattern
                    val = cleaned_value
        
        df_row[p] = val

    ##################

    # NEW: Programmatically override Date Received and Hour Received from all_text header
    # Find the first "Date:" line in the EMAIL CONTENT section
    date_match = re.search(r"EMAIL CONTENT:\s*From:.*?\nTo:.*?\nSubject:.*?\nDate:\s*(.+?)\s*(?:\n|$)", all_text, re.DOTALL | re.I)
    if date_match:
        full_date_str = date_match.group(1).strip()
        try:
            # Parse date (e.g., "Wed, 16 Jul 2025 09:42:39 +0100") into components
            # Extract date part (e.g., "16 Jul 2025")
            date_received = re.search(r"\d{1,2} \w{3} \d{4}", full_date_str).group(0)
            # Extract time part (e.g., "09:42")
            hour_received = re.search(r"\d{2}:\d{2}", full_date_str).group(0)
            
            df_row["Date Received"] = date_received
            df_row["Hour Received"] = hour_received
        except (AttributeError, IndexError):
            pass  # If parsing fails, retain LLM value or set to "Not found"

    ##################
    
    # Override the Reason for Change if enquiry_type was explicitly provided
    if enquiry_type:
        df_row["Reason for Change"] = enquiry_type

    print(f"Parameters extracted from email: {df_row}")
    
    return df_row

def extract_project_name_from_content(email_text, all_extracted_text):
    """
    Extract the project name from email content and attachments.
    
    Args:
        email_text: The email text content
        all_extracted_text: Already extracted text from email and attachments
    
    Returns:
        str: The extracted project name
    """
    # Create a focused prompt for the LLM
    prompt = f"""
    Based on the following email content and attachments, extract the project name (drawing title) which is usually the project location.
    Return only the project name, nothing else.
    
    {all_extracted_text}
    """
    
    # Send to Gemini for analysis
    response = query_llm(prompt, "")
    
    # Add null check before returning
    if response is None:
        return ""
    
    print(f"Project name extracted: {response}")
    
    return response.strip() 