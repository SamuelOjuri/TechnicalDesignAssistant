import re
from flask import current_app
import os

def extract_parameters(all_text):
    """
    Wrapper for parameter extraction to be used by other modules.
    This redirects to the appropriate parameter extraction service.
    """
    from ..services.parameter_extraction import extract_parameters as _extract_parameters
    return _extract_parameters(all_text)

def map_tapered_insulation_value(value):
    """Maps specific insulation product values to their category headers"""
    
    # Define lookup tables based on the image data
    insulation_mappings = {
        "TissueFaced PIR": ["TT47", "TR27", "Glass Tissue PIR", "Powerdeck F", "Adhered", "MG", "TR/MG", "FR/MG", "BauderPIR FA-TE", "Evatherm A", "Hytherm ADH"],
        "TorchOn PIR": ["TT44", "TR24", "Torched", "Powerdeck U", "Torched", "BGM", "TR/BGM", "FR/BGM", "BauderPIR FA"],
        "FoilFaced PIR": ["TT46", "TR26", "Foil", "Powerdeck Eurodeck", "Mech Fixed", "ALU", "TR/ALU", "FR/ALU", "Aluminium Faced"],
        "ROCKWOOL HardRock MultiFix DD": ["Mineral wool", "Hardrock", "stonewool", "stone wool", "rock wool", "bauderrock"],
        "Foamglas T3+": ["Cellular Glass", "foamed glass", "Bauderglas"],
        "EPS": ["Expanded Polystrene"],
        "XPS": ["Extruded Polystyrene"]
    }
    
    # Check if value exactly matches or contains any of the lookup values
    if value and value != "Not found":
        original_value = value
        for category, products in insulation_mappings.items():
            for product in products:
                if product.lower() in value.lower() or value.lower() in product.lower():
                    return category
    
    # Return original value if no match found
    return value

def create_uploads_directory():
    """Create the uploads directory if it doesn't exist"""
    uploads_dir = current_app.config.get('UPLOAD_FOLDER')
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
    return uploads_dir 