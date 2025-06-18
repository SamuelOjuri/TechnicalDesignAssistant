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
    MONDAY_BOARD_ID = "1825117125"  # Board ID for Tapered Enquiry Maintenance
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', os.path.join(os.getcwd(), 'uploads'))
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20MB max file size
