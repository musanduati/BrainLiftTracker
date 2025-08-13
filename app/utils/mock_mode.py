from app.core.config import Config

# Mock mode disabled - we want real Twitter posting
MOCK_TWITTER_POSTING = Config.MOCK_TWITTER_POSTING

# Allow runtime toggle
mock_mode_override = {'enabled': False}

def is_mock_mode():
    """Check if mock mode is enabled"""
    return MOCK_TWITTER_POSTING or mock_mode_override['enabled']

def set_mock_mode(enabled):
    """Enable or disable mock mode at runtime"""
    mock_mode_override['enabled'] = enabled
    return mock_mode_override['enabled']

def get_mock_mode_status():
    """Get current mock mode status"""
    return {
        'enabled': is_mock_mode(),
        'config_setting': MOCK_TWITTER_POSTING,
        'runtime_override': mock_mode_override['enabled']
    }