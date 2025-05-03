from flask import Blueprint, request, jsonify, current_app
from ..services.monday_service import (
    search_monday_projects, 
    get_project_details,
    extract_parameters_from_monday_project
)
from ..utils.monday_dot_com_interface import MondayDotComInterface

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