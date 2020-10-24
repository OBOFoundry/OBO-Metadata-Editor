import os
import textwrap

from logging import DEBUG


# Logging related configuration:
LOG_LEVEL = DEBUG
LOGGING_CONFIG = "%(asctime)-15s %(name)s %(levelname)s - %(message)s"

# Flask config:
FLASK_HOST = os.getenv("FLASK_HOST")

# The filesystem directory where the metadata editor is running from:
PWD = os.path.dirname(os.path.realpath(__file__))

# The github organisation/username to use when communicating with github (e.g. 'OBOFoundry')
GITHUB_ORG = "OBOFoundry"
# The github repository to use for editing PURL configuration (e.g. 'purl.obolibrary.org')
GITHUB_PURL_REPO = "purl.obolibrary.org"
# The directory in which the PURL config files are stored within the PURL repo
GITHUB_PURL_DIR = "config"
# The github repository to use for editing Foundry registry (e.g. 'OBOFoundry.github.io')
GITHUB_FOUNDRY_REPO = "OBOFoundry.github.io"
# The directory in which the Registry config files within the Foundry repo
GITHUB_FOUNDRY_DIR = "ontology"

# File extension for YAML files
YAML_EXT = ".yml"
# File extension for Markdown files
MARKDOWN_EXT = ".md"

# The location to post New Ontology Registration issues to:
REGISTRY_REQUEST = (
    f"https://api.github.com/repos/{GITHUB_ORG}/{GITHUB_FOUNDRY_REPO}/issues"
)

# The location of the PURL validation schema:
PURL_SCHEMA = (
    f"https://github.com/{GITHUB_ORG}/{GITHUB_PURL_REPO}/raw/"
    f"master/tools/config.schema.json"
)
# The location of the REGISTRY validations schema
REGISTRY_SCHEMA = (
    f"https://github.com/{GITHUB_ORG}/{GITHUB_FOUNDRY_REPO}/raw/master/util/"
    f"schema/registry_schema_test.json"
)

# The URL where information (e.g. long names) about ontologies can be retrieved.
ONTOLOGY_METADATA_URL = (
    f"https://github.com/{GITHUB_ORG}/{GITHUB_FOUNDRY_REPO}/raw/"
    f"master/registry/ontologies.yml"
)

# Used to help prevent CSRF attacks:
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")

# Location of the database file:
DATABASE_URI = "sqlite:////tmp/github-flask.db"

# GitHub OAuth parameters used to access the GitHub API
GITHUB_APP_STATE = os.getenv("GITHUB_APP_STATE")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")

# Template used to generate the initial text when launching the editor with a new PURL configuration
# file:
NEW_PROJECT_PURL_TEMPLATE = textwrap.dedent(
    """
  # PURL configuration for http://purl.obolibrary.org/obo/{idspace_lower}

  idspace: {idspace_upper}
  base_url: /obo/{idspace_lower}

  products:
  - {idspace_lower}.owl: https://raw.githubusercontent.com/{org}/{git}/master/{idspace_lower}.owl

  term_browser: ontobee
  """
)

NEW_PROJECT_REGISTRY_TEMPLATE = """---
{yaml_registry_details}
---
{description}
"""

NEW_ONTOLOGY_EMAIL_TEMPLATE = """Dear OBO Foundry,

We would like to request the namespace '{idSpace}' in the OBO Library.

Request prefix: {idSpace}
Ontology title: {ontologyTitle}
Ontology location: {ontoLoc}
Domain: {domain}

The link to the issue is: {issueLink}

Kind regards,
{contactPerson}"""
