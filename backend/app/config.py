import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration settings for the Flask application."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-for-technical-design-assistant')
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    MONDAY_API_TOKEN = os.getenv('MONDAY_API_TOKEN')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    GEMINI_MODEL = "gemini-2.5-flash"  # Current default model
    MONDAY_BOARD_ID = "1825117125"  # Board ID for Tapered Enquiry Maintenance (for project search and data extraction)
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', os.path.join(os.getcwd(), 'uploads'))
    MAX_CONTENT_LENGTH = 30 * 1024 * 1024  # 30MB max file size
    
    # Tier 1 optimized settings
    MAX_CONCURRENT_REQUESTS = int(os.getenv('MAX_CONCURRENT_REQUESTS', '15'))
    MAX_WORKERS = int(os.getenv('MAX_WORKERS', '15'))
    GEMINI_RPM_LIMIT = int(os.getenv('GEMINI_RPM_LIMIT', '950'))