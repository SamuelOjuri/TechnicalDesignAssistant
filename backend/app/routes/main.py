from flask import Blueprint, request, jsonify, current_app, send_file
from werkzeug.utils import secure_filename
import os
import io
import pandas as pd
from ..services.file_processor import process_files, allowed_file
from ..services.parameter_extraction import extract_parameters
from ..services.monday_service import search_monday_projects, get_project_details, extract_parameters_from_monday_project
from ..tasks.file_processing_tasks import process_files_async
from ..utils.progress_tracker import ProgressTracker
import uuid
import base64

main_bp = Blueprint('main', __name__, url_prefix='/api')

@main_bp.route('/process', methods=['POST'])
def process_uploaded_files():
    """
    Process uploaded files asynchronously and return job_id immediately.
    """
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('files')
    
    # Validate files
    for file in files:
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        if not allowed_file(file.filename):
            return jsonify({'error': f'File type not allowed: {file.filename}'}), 400
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    # Prepare file data for background processing
    files_data = []
    for file in files:
        filename = secure_filename(file.filename)
        content = file.read()
        files_data.append({
            'filename': filename,
            'content': base64.b64encode(content).decode('utf-8'),  # Encode binary data
            'size': len(content)
        })
    
    # Start background task
    task = process_files_async.delay(files_data, job_id)
    
    # Return job_id immediately
    return jsonify({
        'job_id': job_id,
        'task_id': task.id,
        'status': 'processing',
        'message': 'Files are being processed in the background'
    })

@main_bp.route('/progress/<job_id>', methods=['GET'])
def get_progress(job_id):
    """Get progress for a specific job."""
    progress_tracker = ProgressTracker(job_id)
    progress = progress_tracker.get_progress()
    
    if not progress:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify(progress)

@main_bp.route('/download-excel', methods=['POST'])
def download_excel():
    """
    Create Excel file from parameters and optional LLM response.
    ---
    Returns:
        Excel file download
    """
    data = request.json
    if not data or 'params' not in data:
        return jsonify({'error': 'No parameters provided'}), 400
    
    params = data['params']
    extra_llm_response = data.get('llm_response')
    
    df = pd.DataFrame([params])
    
    # Create Excel file in memory
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Parameters")
        if extra_llm_response:
            pd.DataFrame({"Response": [extra_llm_response]}).to_excel(writer, index=False, sheet_name="Full Response")
    buffer.seek(0)
    
    # Set proper headers for file download
    return send_file(
        buffer,
        download_name="Technical_Parameters.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@main_bp.route('/monday/search', methods=['POST'])
def search_projects():
    """
    Search for similar projects in Monday.com.
    ---
    Returns:
        JSON with search results
    """
    data = request.json
    if not data or 'project_name' not in data:
        return jsonify({'error': 'No project name provided'}), 400
    
    project_name = data['project_name']
    monday_api_token = current_app.config['MONDAY_API_TOKEN']
    
    if not monday_api_token:
        return jsonify({'error': 'Monday.com API token not configured'}), 500
    
    results = search_monday_projects(project_name, monday_api_token)
    return jsonify(results)

@main_bp.route('/monday/project/<project_id>', methods=['GET'])
def get_project(project_id):
    """
    Get detailed information about a project from Monday.com.
    ---
    Returns:
        JSON with project details
    """
    board_id = current_app.config['MONDAY_BOARD_ID']  # Get the board ID from config
    monday_api_token = current_app.config['MONDAY_API_TOKEN']
    
    if not monday_api_token:
        return jsonify({'error': 'Monday.com API token not configured'}), 500
    
    project_details, error = get_project_details(project_id, board_id, monday_api_token)
    
    if error:
        return jsonify({'error': error}), 404
    
    # Extract parameters from project details
    params = extract_parameters_from_monday_project(project_details)
    
    return jsonify({
        'project_details': project_details,
        'params': params
    })

@main_bp.route('/monday/extract-params', methods=['POST'])
def extract_project_params():
    """
    Extract parameters from a Monday.com project.
    ---
    Returns:
        JSON with extracted parameters
    """
    data = request.json
    if not data or 'project_details' not in data:
        return jsonify({'error': 'No project details provided'}), 400
    
    project_details = data['project_details']
    params = extract_parameters_from_monday_project(project_details)
    
    return jsonify({'params': params}) 