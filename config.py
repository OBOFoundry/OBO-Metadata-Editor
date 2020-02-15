import os
import textwrap

from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL


# Logging related configuration:
LOG_LEVEL = DEBUG
LOGGING_CONFIG = '%(asctime)-15s %(name)s %(levelname)s - %(message)s'

FLASK_HOST = ''
FLASK_PORT = 5000

# The filesystem directory where purl-edtor is running from:
PWD = os.path.dirname(os.path.realpath(__file__))

# The github organisation/username to use when communicating with github (e.g. 'OBOFoundry')
GITHUB_ORG = 'lmcmicu'
# The github repository to use when communicating with github (e.g. 'purl.obolibrary.org')
GITHUB_REPO = 'purl.obolibrary.org'

# The location of the validation schema:
SCHEMAFILE = "{}/../purl.obolibrary.org/tools/config.schema.json".format(PWD)

# The URL where information (e.g. long names) about ontologies can be retrieved.
ONTOLOGY_METADATA_URL = \
  'https://github.com/OBOFoundry/OBOFoundry.github.io/raw/master/registry/ontologies.yml'

# Used to help prevent CSRF attacks:
FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY')

# Location of the database file:
DATABASE_URI = 'sqlite:////tmp/github-flask.db'

# GitHub OAuth parameters used to access the GitHub API
GITHUB_OAUTH_APP_NAME = 'purl_editor'
GITHUB_OAUTH_STATE = os.getenv('GITHUB_OAUTH_STATE')
GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID')
GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET')

# Template used to generate the initial text when launching the editor with a new configuration
# file:
NEW_PROJECT_TEMPLATE = textwrap.dedent(
  """
  # PURL configuration for http://purl.obolibrary.org/obo/{idspace_lower}

  idspace: {idspace_upper}
  base_url: /obo/{idspace_lower}

  products:
  - {idspace_lower}.owl: https://raw.githubusercontent.com/{org}/{git}/master/{idspace_lower}.owl

  term_browser: ontobee
  """)
