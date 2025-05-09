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

def extract_parameters_from_monday_project(project_details):
    """
    Extracts design parameters from a Monday.com project.
    
    Args:
        project_details: The project details from Monday.com
        
    Returns:
        dict: A dictionary of extracted parameters
    """
    # Initialize parameters with default values
    params = {
        "Post Code": "Not found",
        "Drawing Reference": "Not found",
        "Drawing Title": "Not found",
        "Revision": "Not found",
        "Date Received": "Not found",
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
        # Use the most recent subitem (revision) for detailed information
        # Sort by ID in descending order to get the most recent one
        latest_subitem = sorted(project_details['subitems'], key=lambda x: x['id'], reverse=True)[0]
        
        # Extract Drawing Reference from subitem name
        if '_' in latest_subitem['name']:
            # The entire name (e.g., "16903_25.01 - A") should be used as Drawing Reference
            params["Drawing Reference"] = latest_subitem['name']  # Use the full name
        
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
        for col in latest_subitem.get('column_values', []):
            col_id = col.get('id')
            if col_id in column_mappings:
                param_name = column_mappings[col_id]
                
                # Try to get text value or display_value for MirrorValue
                if col.get('text') and col.get('text') != "None":
                    params[param_name] = col.get('text')
                elif col.get('__typename') == "MirrorValue" and col.get('display_value'):
                    params[param_name] = col.get('display_value')
        
        
    return params 