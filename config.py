import os
from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL

LOG_LEVEL = DEBUG

# TODO: ADD SOMETHING TO SAY WE WANT 'OBOFoundry/purl.obolibrary.org' for editing files.

ONTOLOGY_METADATA_URL = \
  'https://github.com/OBOFoundry/OBOFoundry.github.io/raw/master/registry/ontologies.yml'
FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY')
DATABASE_URI = 'sqlite:////tmp/github-flask.db'
GITHUB_OAUTH_APP_NAME = 'purl_editor'
GITHUB_OAUTH_STATE = os.getenv('GITHUB_OAUTH_STATE')
GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID')
GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET')
