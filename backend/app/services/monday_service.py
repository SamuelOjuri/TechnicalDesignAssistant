import re
from datetime import datetime
from ..utils.monday_dot_com_interface import MondayDotComInterface
import json

def search_monday_projects(project_name, monday_api_token):
    """
    Search for projects in Monday.com by name.
    
    Args:
        project_name: Name of the project to search for
        monday_api_token: Monday.com API token
        
    Returns:
        Dictionary with search results
    """
    monday = MondayDotComInterface(monday_api_token)
    
    try:
        # No need for the extra query - just use check_project_exists directly
        results = monday.check_project_exists(project_name)
        return results
        
    except Exception as e:
        print(f"Error searching for projects: {e}")
        return {"exists": False, "error": str(e), "matches": []}

def get_project_details(project_id, board_id, monday_api_token):
    """
    Get detailed information about a project from Monday.com.
    
    Args:
        project_id: ID of the project in Monday.com
        board_id: ID of the board containing the project
        monday_api_token: API token for Monday.com
    
    Returns:
        tuple: (project_details, error)
    """
    monday_interface = MondayDotComInterface(monday_api_token)
    
    # Get project directly by ID instead of the two-step process
    return monday_interface.get_project_by_id(project_id)

def extract_parameters_from_monday_project(project_details, target_drawing_ref=None):
    """
    Extracts design parameters from a Monday.com project.
    
    Args:
        project_details: The project details from Monday.com
        target_drawing_ref: Optional target drawing reference for specific extraction
        
    Returns:
        dict: A dictionary of extracted parameters
    """
    # Initialize parameters with default values
    params = {
        "Email Subject": "Not found",
        "Post Code": "Not found",
        "Drawing Reference": "Not found",
        "Drawing Title": "Not found",
        "Revision": "Not found",
        "Date Received": "Not found",
        "Hour Received": "Not found",
        "Company": "Not found",
        "Contact": "Not found",
        "Reason for Change": "Amendment",  # Default for existing projects
        "Surveyor": "Not found",
        "Target U-Value": "Not found",
        "Target Min U-Value": "Not found", 
        "Fall of Tapered": "Not found",
        "Tapered Insulation": "Not found",
        "Decking": "Not found"
    }
    
    # First, extract data from main project item
    for col in project_details.get('column_values', []):
        # Extract Post Code from dropdown_mknfpjbt column (Zip Code)
        if col.get('id') == "dropdown_mknfpjbt" and col.get('text'):
            params["Post Code"] = col.get('text')
        
        # Extract Project Name
        elif col.get('id') == "text3__1":  # Project Name column
            if col.get('text'):
                params["Drawing Title"] = col.get('text')
            elif col.get('__typename') == "MirrorValue" and col.get('display_value'):
                params["Drawing Title"] = col.get('display_value')
    
    # Get today's date for Date Received (for amendments)
    params["Date Received"] = datetime.now().strftime("%Y-%m-%d")
    
    # Check if we have subitems (revisions) with more detailed information
    if project_details.get('subitems') and len(project_details['subitems']) > 0:
        selected_subitem = None
        
        if target_drawing_ref:
            # Try to find subitem matching the target drawing reference
            for subitem in project_details['subitems']:
                if subitem['name'] == target_drawing_ref:
                    selected_subitem = subitem
                    break
        
        # If no specific target or no match found, use latest revision logic
        if not selected_subitem:
            # Filter non-archived subitems
            active_subitems = []
            
            for subitem in project_details['subitems']:
                # Check status from mirror columns
                status = None
                for col in subitem.get('column_values', []):
                    if col.get('id') == 'mirror11__1' and col.get('display_value'):
                        status = col.get('display_value')
                        break
                
                # Only include non-archived items
                if status != "Archived":
                    active_subitems.append(subitem)
            
            if active_subitems:
                # Sort by version number first (highest), then by revision letter (highest)
                def extract_version_and_revision(subitem_name):
                    """
                    Extract version number and revision letter from subitem name.
                    Examples:
                    - '16763_25.01 - A' -> (25.01, 'A')
                    - '5327_19.01 - D' -> (19.01, 'D')
                    - '9420_22.01 - B' -> (22.01, 'B')
                    """
                    import re
                    # Match pattern: PROJECT_VERSION.SUBVERSION - LETTER
                    match = re.search(r'_(\d+\.\d+)\s*-\s*([A-Z])', subitem_name)
                    if match:
                        version_str = match.group(1)  # e.g., "25.01"
                        letter = match.group(2)       # e.g., "A"
                        version_num = float(version_str)  # Convert to float for sorting
                        return (version_num, letter)
                    
                    # Fallback: try to extract just the letter for older naming schemes
                    letter_match = re.search(r'- ([A-Z])(?:\s|$|\()', subitem_name)
                    if letter_match:
                        return (0.0, letter_match.group(1))
                    
                    return (0.0, 'A')  # Default fallback
                
                # Sort by version number first (highest), then by revision letter (highest)
                active_subitems.sort(
                    key=lambda x: extract_version_and_revision(x['name']), 
                    reverse=True
                )
                selected_subitem = active_subitems[0]  # Take highest version/revision
            else:
                # Fall back to highest ID if all are archived
                selected_subitem = sorted(project_details['subitems'], key=lambda x: x['id'], reverse=True)[0]
        
        # Extract Drawing Reference from selected subitem name
        if selected_subitem and '_' in selected_subitem['name']:
            params["Drawing Reference"] = selected_subitem['name']
        
        # Map column IDs to parameter names for subitem values
        column_mappings = {
            # Direct mappings from Monday.com column IDs to our parameter names
            "mirror_12__1": "Company",           # Account column
            "mirror39__1": "Designer",           # Designer column
            "mirror_11__1": "Contact",           # Contact column
            "mirror92__1": "Surveyor",           # Surveyor column
            "mirror0__1": "Target U-Value",      # U-Value column
            "mirror12__1": "Target Min U-Value", # Min U-Value column
            "mirror22__1": "Fall of Tapered",    # Fall column
            "mirror875__1": "Tapered Insulation", # Product Type column
            "mirror75__1": "Decking",            # Deck Type column
            "mirror95__1": "Date Received",      # Date Received column
            "mirror03__1": "Reason for Change",  # Reason For Change column
            "mirror_1__1": "Revision",           # Revision column
        }
        
        # Process each column value in the subitem
        for col in selected_subitem.get('column_values', []):
            col_id = col.get('id')
            if col_id in column_mappings:
                param_name = column_mappings[col_id]
                
                # Try to get text value or display_value for MirrorValue
                if col.get('text') and col.get('text') != "None":
                    params[param_name] = col.get('text')
                elif col.get('__typename') == "MirrorValue" and col.get('display_value'):
                    params[param_name] = col.get('display_value')
        
    # After all extraction logic and just before the return statement
    print("=== Parameters extracted from Monday.com ===")
    for key, value in params.items():
        print(f"  {key}: {value}")
    print("============================================")
    
    return params 