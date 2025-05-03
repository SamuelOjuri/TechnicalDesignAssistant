from flask import Flask, jsonify, redirect, send_from_directory
from flask_cors import CORS
from .config import Config
import os

def create_app(config_class=Config):
    """Initialize Flask app with configurations and register blueprints."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # CORS ─ allow any origin **only for our API routes** and make sure the
    #        automatic pre-flight handler is enabled.
    CORS(
        app,
        resources={r"/api/*": {
            "origins": [
                "http://localhost:3000",
                "https://technical-design-assistant.netlify.app"
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True,
            "expose_headers": ["Content-Type", "X-CSRFToken"],
            "max_age": 600
        }},
        automatic_options=True
    )

    # Root route
    @app.route('/')
    def index():
        return jsonify({
            "name": "Technical Design Assistant API",
            "version": "1.0.0",
            "endpoints": {
                "file_processing": "/api/process",
                "chat": "/api/chat",
                "monday": "/api/monday/search, /api/monday/project/<id>"
            },
            "status": "online"
        })
    
    # Handle favicon.ico requests
    @app.route('/favicon.ico')
    def favicon():
        return "", 204  # Return no content

    # Register blueprints
    from .routes.main import main_bp
    from .routes.monday import monday_bp
    from .routes.chat import chat_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(monday_bp)
    app.register_blueprint(chat_bp)

    return app
