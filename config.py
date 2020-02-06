import os

DEBUG_ENABLED = False

OAUTH_APP_NAME = 'purl_editor'
ACCESS_TOKEN_URL = 'https://github.com/login/oauth/access_token'
ACCESS_TOKEN_PARAMS = None
AUTHORIZE_URL = 'https://github.com/login/oauth/authorize'
AUTHORIZE_PARAMS = None
API_BASE_URL = 'https://api.github.com/'

FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY')

# These environment variables need to be defined to enable integration with github:
GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID')
GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET')
