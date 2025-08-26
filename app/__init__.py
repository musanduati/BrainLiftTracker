from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import os
from datetime import datetime, timezone
try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc

from app.core.config import Config
from app.db.database import init_database

def create_app():
    """Application factory for creating Flask app"""
    app = Flask(__name__)
    
    # Configure app
    app.config.from_object(Config)
    
    # Enable CORS for the frontend
    CORS(app, origins=Config.CORS_ORIGINS, supports_credentials=True)
    
    # Initialize database
    init_database()
    
    # Register blueprints
    from app.api.auth.routes import auth_bp
    from app.api.accounts.routes import accounts_bp
    from app.api.tweets.routes import tweets_bp
    from app.api.threads.routes import threads_bp
    from app.api.lists.routes import lists_bp
    from app.api.utils.routes import utils_bp
    from app.api.analytics.routes import analytics_bp
    from app.api.oauth1.routes import oauth1_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(tweets_bp)
    app.register_blueprint(threads_bp)
    app.register_blueprint(lists_bp)
    app.register_blueprint(utils_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(oauth1_bp)
    
    # Register basic routes
    @app.route('/api/v1/health', methods=['GET'])
    def health():
        """Health check - no auth required"""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now(UTC).isoformat(),
            'version': '2.0.0-modular'
        })
    
    @app.route('/api/v1/test', methods=['GET'])
    def test():
        """Test endpoint with API key"""
        from app.utils.security import check_api_key
        if not check_api_key():
            return jsonify({'error': 'Invalid API key'}), 401
        
        return jsonify({
            'status': 'success',
            'message': 'API key validated!'
        })
    
    @app.route('/api/v1/mock-mode', methods=['GET', 'POST'])
    def mock_mode():
        """Get or set mock mode"""
        from flask import request
        from app.utils.security import check_api_key
        from app.utils.mock_mode import get_mock_mode_status, set_mock_mode
        
        if not check_api_key():
            return jsonify({'error': 'Invalid API key'}), 401
        
        if request.method == 'POST':
            data = request.get_json()
            if data and 'enabled' in data:
                enabled = set_mock_mode(data['enabled'])
                return jsonify({
                    'message': f"Mock mode {'enabled' if enabled else 'disabled'}",
                    'mock_mode': enabled
                })
        
        status = get_mock_mode_status()
        return jsonify({'mock_mode': status['runtime_override']})
    
    # Frontend serving routes
    @app.route('/')
    def serve_frontend():
        """Serve the React frontend"""
        frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'twitter-manager-frontend', 'dist')
        if os.path.exists(os.path.join(frontend_path, 'index.html')):
            return send_from_directory(frontend_path, 'index.html')
        else:
            return jsonify({'message': 'Frontend not built. Run: cd twitter-manager-frontend && npm run build'}), 404
    
    @app.route('/assets/<path:path>')
    def serve_assets(path):
        """Serve frontend assets"""
        frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'twitter-manager-frontend', 'dist', 'assets')
        return send_from_directory(frontend_path, path)
    
    # Catch-all route for React Router
    @app.route('/<path:path>')
    def catch_all(path):
        """Handle React Router routes"""
        # Don't catch API routes
        if path.startswith('api/'):
            return jsonify({'error': 'Not found'}), 404
        
        frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'twitter-manager-frontend', 'dist')
        if os.path.exists(os.path.join(frontend_path, 'index.html')):
            return send_from_directory(frontend_path, 'index.html')
        else:
            return jsonify({'error': 'Not found'}), 404
    
    return app