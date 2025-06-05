from flask import Blueprint, request, jsonify, current_app
from ..services.monday_service import (
    search_monday_projects, 
    get_project_details,
    extract_parameters_from_monday_project
)
from ..utils.monday_dot_com_interface import MondayDotComInterface
import json
from datetime import datetime
import re

monday_bp = Blueprint('monday', __name__, url_prefix='/api/monday')

@monday_bp.route('/search', methods=['POST'])
def search_projects():
    """
    Search for projects in Monday.com by name.
    ---
    Args:
        project_name: Name of the project to search for
    
    Returns:
        JSON with search results
    """
    data = request.json
    if not data or 'project_name' not in data:
        return jsonify({'error': 'No project name provided'}), 400
    
    project_name = data['project_name']
    
    # Get Monday.com interface from app config
    monday_api_token = current_app.config['MONDAY_API_TOKEN']
    if not monday_api_token:
        return jsonify({'error': 'Monday.com API token not configured'}), 500
    
    results = search_monday_projects(project_name, monday_api_token)
    return jsonify(results)

@monday_bp.route('/project/<project_id>', methods=['GET'])
def get_project(project_id):
    """
    Get detailed project information from Monday.com.
    ---
    Args:
        project_id: ID of the project in Monday.com
    
    Returns:
        JSON with project details and extracted parameters
    """
    monday_api_token = current_app.config['MONDAY_API_TOKEN']
    if not monday_api_token:
        return jsonify({'error': 'Monday.com API token not configured'}), 500
    
    # No need to pass the board_id since we're using a direct project ID lookup
    project_details, error = get_project_details(project_id, None, monday_api_token)
    
    if error:
        return jsonify({'error': error}), 404
    
    # Extract parameters from project details
    params = extract_parameters_from_monday_project(project_details)
    
    return jsonify({
        'params': params,
        'project_details': project_details
    })

@monday_bp.route('/extract-parameters/<project_id>', methods=['GET'])
def extract_monday_parameters(project_id):
    """
    Extract parameters from a Monday.com project.
    ---
    Args:
        project_id: ID of the project in Monday.com
    
    Returns:
        JSON with extracted parameters
    """
    monday_api_token = current_app.config['MONDAY_API_TOKEN']
    if not monday_api_token:
        return jsonify({'error': 'Monday.com API token not configured'}), 500
    
    board_id = current_app.config['MONDAY_BOARD_ID']
    
    project_details, error = get_project_details(project_id, board_id, monday_api_token)
    
    if error:
        return jsonify({'error': error}), 400
    
    parameters = extract_parameters_from_monday_project(project_details)
    
    return jsonify({
        'params': parameters,
        'project_details': project_details
    })

@monday_bp.route('/search', methods=['OPTIONS'])
def options_search():
    response = current_app.make_default_options_response()
    return response

@monday_bp.route('/project/<project_id>', methods=['OPTIONS'])
def options_project(project_id):
    response = current_app.make_default_options_response()
    return response

@monday_bp.route('/board/<board_id>/columns', methods=['GET'])
def get_board_columns(board_id):
    """
    Get all columns for a board with their IDs and titles.
    This helps map column titles to IDs dynamically.
    """
    monday_api_token = current_app.config['MONDAY_API_TOKEN']
    if not monday_api_token:
        return jsonify({'error': 'Monday.com API token not configured'}), 500
    
    monday = MondayDotComInterface(monday_api_token)
    
    query = """
    query ($boardId: ID!) {
        boards(ids: [$boardId]) {
            columns {
                id
                title
                type
            }
        }
    }
    """
    
    variables = {"boardId": int(board_id)}
    result = monday.execute_query(query, variables)
    
    if result and "data" in result and "boards" in result["data"]:
        columns = result["data"]["boards"][0]["columns"]
        # Create a mapping of title to ID
        column_mapping = {col["title"]: col["id"] for col in columns}
        return jsonify({
            'columns': columns,
            'mapping': column_mapping
        })
    
    return jsonify({'error': 'Failed to fetch columns'}), 500

def clean_extracted_value(value):
    """
    Clean extracted values that may have extra formatting characters.
    Removes patterns like '": "value",' to just 'value'
    """
    if not value:
        return value
    
    # Convert to string if not already
    value_str = str(value)
    
    # Remove common patterns from malformed extraction
    # Pattern: '": "actual_value",' or variations
    
    # Try to extract the actual value from patterns like '": "value",'
    match = re.search(r'["\']?\s*:\s*["\']([^"\']+)["\']', value_str)
    if match:
        return match.group(1).strip()
    
    # If no pattern matches, just strip quotes and whitespace
    return value_str.strip(' "\',')

def format_date_for_monday(date_string):
    """
    Convert date string to Monday.com format.
    Monday.com expects dates in YYYY-MM-DD format.
    """
    if not date_string:
        return ""
    
    # Clean the date string first
    date_string = clean_extracted_value(date_string)
    
    # Try to parse common date formats
    date_formats = [
        "%d/%m/%Y",      # DD/MM/YYYY (25/02/2025)
        "%d-%m-%Y",      # DD-MM-YYYY
        "%Y-%m-%d",      # YYYY-MM-DD (already correct format)
        "%d %b %Y",      # DD Mon YYYY (25 Feb 2025)
        "%d %B %Y",      # DD Month YYYY (25 February 2025)
        "%d/%m/%y",      # DD/MM/YY
        "%d-%m-%y",      # DD-MM-YY
    ]
    
    for fmt in date_formats:
        try:
            date_obj = datetime.strptime(date_string.strip(), fmt)
            # Return in Monday.com's expected format
            return date_obj.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    # If we can't parse the date, return empty string
    print(f"Warning: Could not parse date '{date_string}'")
    return ""

def format_hour_for_monday(time_string):
    """
    Convert time string to Monday.com hour format.
    Monday.com expects hour columns as {"hour": 17, "minute": 6} format.
    """
    if not time_string:
        return None
    
    # Clean the time string first
    time_string = clean_extracted_value(time_string)
    
    # Try to parse common time formats
    import re
    
    # Match patterns like "17:06", "17.06", "5:30 PM", etc.
    # First try 24-hour format
    match = re.match(r'^(\d{1,2})[:\.](\d{2})$', time_string.strip())
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        return {"hour": hour, "minute": minute}
    
    # Try 12-hour format with AM/PM
    match = re.match(r'^(\d{1,2})[:\.](\d{2})\s*(AM|PM|am|pm)$', time_string.strip())
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        meridiem = match.group(3).upper()
        
        # Convert to 24-hour format
        if meridiem == 'PM' and hour != 12:
            hour += 12
        elif meridiem == 'AM' and hour == 12:
            hour = 0
            
        return {"hour": hour, "minute": minute}
    
    print(f"Warning: Could not parse time '{time_string}'")
    return None

def format_dropdown_for_monday(value, settings_str):
    """
    Convert dropdown value to Monday.com format.
    Monday.com expects dropdown columns as {"ids": [option_id]} format.
    
    Args:
        value: The text value to convert (e.g., "New Enquiry", "Amendment")
        settings_str: The JSON settings string from the column definition
        
    Returns:
        dict: Formatted value for Monday.com API or None if not found
    """
    if not value or not settings_str:
        return None
    
    try:
        settings = json.loads(settings_str)
        labels = settings.get("labels", [])
        
        # Find the matching label by name
        for label in labels:
            if label.get("name") == value:
                return {"ids": [label.get("id")]}
        
        print(f"Warning: Could not find dropdown option '{value}' in settings")
        return None
    except json.JSONDecodeError:
        print(f"Warning: Could not parse dropdown settings: {settings_str}")
        return None

@monday_bp.route('/create-item', methods=['POST'])
def create_monday_item():
    """
    Create a new item in Monday.com board.
    Accepts column values by title and automatically maps to IDs.
    """
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    required_fields = ['board_id', 'group_id', 'item_name', 'column_values_by_title']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    monday_api_token = current_app.config['MONDAY_API_TOKEN']
    if not monday_api_token:
        return jsonify({'error': 'Monday.com API token not configured'}), 500
    
    try:
        monday = MondayDotComInterface(monday_api_token)
        
        # First, get the column mapping for this board
        board_id = data['board_id']
        query = """
        query ($boardId: ID!) {
            boards(ids: [$boardId]) {
                columns {
                    id
                    title
                    type
                    settings_str
                }
            }
        }
        """
        
        variables = {"boardId": board_id}
        result = monday.execute_query(query, variables)
        
        if not result or "data" not in result:
            return jsonify({'error': 'Failed to fetch board columns'}), 500
        
        columns = result["data"]["boards"][0]["columns"]
        
        # Create mappings for both title->id and id->type
        title_to_id = {}
        id_to_type = {}
        id_to_settings = {}
        for col in columns:
            title_to_id[col["title"]] = col["id"]
            id_to_type[col["id"]] = col["type"]
            id_to_settings[col["id"]] = col.get("settings_str", "{}")
        
        # Map the column values from titles to IDs and format them properly
        column_values_by_id = {}
        column_values_by_title = data['column_values_by_title']
        
        for title, value in column_values_by_title.items():
            if title not in title_to_id:
                print(f"Unknown column title '{title}' – skipping")
                continue

            column_id   = title_to_id[title]
            column_type = id_to_type[column_id]
            cleaned     = clean_extracted_value(value)

            # Add debug logging
            print(f"Processing column: {title} -> {column_id} (type: {column_type}) with value: '{value}' -> cleaned: '{cleaned}'")

            # ---------- board-relation (TP Ref) -------------------------
            if column_type == "board_relation":
                print(f"Detected board-relation column: {title}")
                if not cleaned:
                    print(f"TP Ref empty – skipping")
                    continue

                # Which board is this relation pointing to?
                try:
                    settings_str = id_to_settings[column_id]
                    print(f"Settings string for {column_id}: {settings_str}")
                    settings = json.loads(settings_str)
                    linked_board = settings.get("boardIds", [])
                    print(f"Linked boards from settings: {linked_board}")
                    
                    if not linked_board:
                        print("No linked board id in settings – skipping TP Ref")
                        continue
                    linked_board_id = linked_board[0]
                    print(f"Using linked board ID: {linked_board_id}")

                    # Try to find an item whose NAME == cleaned (e.g. "16771")
                    print(f"Searching for item '{cleaned}' on board {linked_board_id}")
                    item_id = monday.get_item_id_by_exact_name(linked_board_id, cleaned)
                    print(f"Search result: item_id = {item_id}")
                    
                    if item_id is None:
                        print(f"No exact match for TP Ref '{cleaned}' on board {linked_board_id}")
                        # Nothing is added – the column is simply omitted
                        continue

                    # Correct format for connect-boards column
                    print(f"Adding board-relation value: {{'item_ids': ['{item_id}']}}")
                    column_values_by_id[column_id] = {"item_ids": [str(item_id)]}
                    continue   # done with this column
                except Exception as e:
                    print(f"Exception in board-relation handling: {e}")
                    import traceback
                    traceback.print_exc()
                    continue

            # ---------- date column ------------------------------------
            if column_type == "date" and cleaned:
                iso = format_date_for_monday(cleaned)
                if iso:
                    column_values_by_id[column_id] = iso
                continue

            # ---------- hour column ------------------------------------
            if column_type == "hour" and cleaned:
                hr = format_hour_for_monday(cleaned)
                if hr:
                    column_values_by_id[column_id] = hr
                continue

            # ---------- dropdown column --------------------------------
            if column_type == "dropdown" and cleaned:
                dropdown_value = format_dropdown_for_monday(cleaned, id_to_settings[column_id])
                if dropdown_value:
                    column_values_by_id[column_id] = dropdown_value
                continue

            # ---------- every other column -----------------------------
            if cleaned:
                column_values_by_id[column_id] = cleaned

        # Debug log to see what we're sending
        print(f"Column values being sent to Monday.com: {column_values_by_id}")
        
        # Create the item with mapped column IDs
        mutation = """
        mutation ($boardId: ID!, $groupId: String!, $itemName: String!, $columnValues: JSON!) {
            create_item(
                board_id: $boardId,
                group_id: $groupId,
                item_name: $itemName,
                column_values: $columnValues
            ) {
                id
                name
            }
        }
        """
        
        # Clean the item name as well
        item_name = clean_extracted_value(data['item_name']) if data['item_name'] else 'New Item'
        
        variables = {
            "boardId": board_id,
            "groupId": data['group_id'],
            "itemName": item_name,
            "columnValues": json.dumps(column_values_by_id)
        }
        
        result = monday.execute_query(mutation, variables)
        
        if result and "data" in result and "create_item" in result["data"]:
            created_item = result["data"]["create_item"]
            return jsonify({
                'success': True,
                'id': created_item['id'],
                'name': created_item['name'],
                'column_mapping_used': column_values_by_id
            })
        else:
            error_msg = "Failed to create item"
            if result and "errors" in result:
                error_msg = f"Monday.com API error: {result['errors']}"
            return jsonify({'error': error_msg}), 500
            
    except Exception as e:
        print(f"Error creating Monday.com item: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# Add OPTIONS handler if it doesn't exist
@monday_bp.route('/create-item', methods=['OPTIONS'])
def options_create_item():
    response = current_app.make_default_options_response()
    return response 