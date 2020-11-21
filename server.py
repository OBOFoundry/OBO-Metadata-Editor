#!/usr/bin/env python3

import base64
import functools
import json
import jsonschema
import logging
import re
import requests

from io import StringIO
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from ruamel.yaml.constructor import DuplicateKeyError

from datetime import datetime
from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    Response,
    g,
    send_from_directory,
    session,
    redirect,
    url_for,
)
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from urllib.parse import parse_qs, urlencode
from urllib.request import urlopen

yaml = YAML()  # For parsing yaml files

# To run in development mode, do:
# export FLASK_APP=server.py
# export FLASK_DEBUG=1 (optional)
# export FLASK_ENV=development (optional)
# python3 -m flask run

# Note that the following environment variables must be set:
# GITHUB_CLIENT_ID
# GITHUB_CLIENT_SECRET
# GITHUB_APP_STATE
# FLASK_SECRET_KEY
# FLASK_HOST

# Setup the webapp:
app = Flask(__name__)
app.config.from_object("config")
app.secret_key = app.config["FLASK_SECRET_KEY"]

# Initialize the logger:
logging.basicConfig(format=app.config["LOGGING_CONFIG"])
logger = logging.getLogger(__name__)
logger.setLevel(app.config["LOG_LEVEL"])

# The filesystem directory where this script is running from:
pwd = app.config["PWD"]

# Setup sqlalchemy to manage the database of logged in users:
engine = create_engine(app.config["DATABASE_URI"])
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()

# Boolean for managing current running state feature (show/hide in-development features)
dev = app.config["ENV"] == "development"


# Utility dictionary for linking editor types to repositories and content directories
editor_types = {
    "purl": {
        "repo": app.config["GITHUB_PURL_REPO"],
        "dir": app.config["GITHUB_PURL_DIR"],
    },
    "registry": {
        "repo": app.config["GITHUB_FOUNDRY_REPO"],
        "dir": app.config["GITHUB_FOUNDRY_DIR"],
    },
}


# Retrieve the ontology metadata:
try:
    ontology_md = urlopen(app.config["ONTOLOGY_METADATA_URL"])
    if ontology_md.getcode() == 200:
        ontology_md = yaml.load(ontology_md.read())["ontologies"]
except Exception as e:
    logger.error(f"Could not retrieve ontology metadata: {e}")
    ontology_md = {}


# Load the PURL validation schema:
try:
    purl_schema_text = urlopen(app.config["PURL_SCHEMA"])
    if purl_schema_text.getcode() == 200:
        purl_schema = json.load(purl_schema_text)
except Exception as e:
    logger.error(f"Could not retrieve PURL schema: {e}")
    purl_schema = {}

# Load the REGISTRY validation schema:
try:
    registry_schema_text = urlopen(app.config["REGISTRY_SCHEMA"])
    if registry_schema_text.getcode() == 200:
        registry_schema = json.load(registry_schema_text)
except Exception as e:
    logger.error(f"Could not retrieve REGISTRY schema: {e}")
    registry_schema = {}

# URLs and functions used for communicating with GitHub:
GITHUB_DEFAULT_API_HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "purl-editor/1.0",
}
GITHUB_API_URL = "https://api.github.com"
GITHUB_OAUTH_URL = "https://github.com/login/oauth"


def github_authorize(params):
    """
    Call the /authorize endpoint of GitHub's authorization API to authenticate using the given
    authentication parameters and return GitHub's response.
    """
    response = requests.get(GITHUB_OAUTH_URL + "/authorize", params)
    if not response.ok:
        response.raise_for_status()
    return response


def github_authorize_token(params):
    """
    Call the /access_token endpoint of GitHub's authorization API to authenticate using the given
    authentication parameters and return GitHub's response, which should contain an access token.
    """
    response = requests.post(GITHUB_OAUTH_URL + "/access_token", params)
    if not response.ok:
        response.raise_for_status()
    return response


def github_call(method, endpoint, params={}):
    """
    Call the GitHub REST API at the given endpoint using the given method and passing the given
    params.
    """
    method = method.casefold()
    if method not in ["get", "post", "put"]:
        logger.error(f"Unsupported API method: {method}")
        return {}

    access_token = g.user.github_access_token
    if not access_token:
        logger.error("No token found in the global application context.")
        return {}

    api_headers = GITHUB_DEFAULT_API_HEADERS
    api_headers["Authorization"] = f"token {access_token}"
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint

    fargs = {"url": GITHUB_API_URL + endpoint, "headers": api_headers, "json": params}
    if method == "get":
        # GET parameters must go in URL - https://developer.github.com/v3/#parameters
        if len(params) > 0:
            fargs["url"] = fargs["url"] + "?" + urlencode(params)
        response = requests.get(**fargs)
    elif method == "post":
        response = requests.post(**fargs)
    elif method == "put":
        response = requests.put(**fargs)

    if not response.ok:
        if response.status_code == 403:
            logger.error(
                f"Received 403 Forbidden from {method} request to endpoint {endpoint}"
                "with params {params}"
            )
        response.raise_for_status()
    return response.json()


class User(Base):
    """
    Saved information for users that have been authenticated to the metadata editor.
    Note that this table preserves historical data (user records are not deleted
    when a user logs out)
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    github_access_token = Column(String(255))
    github_id = Column(Integer)
    github_login = Column(String(255))

    def __init__(self, github_access_token):
        self.github_access_token = github_access_token


@app.before_request
def before_request():
    """
    Called at the beginning of every request to set the global application context.
    """
    # Reset the user information that is saved in the global context. If the session
    # already contains user information, use that to populate the global context, otherwise
    # leave it unset.
    g.user = None
    if "user_id" in session:
        g.user = User.query.get(session["user_id"])


@app.after_request
def after_request(response):
    """
    Called at the end of every request.
    """
    # Clean up the database session:
    db_session.remove()
    return response


@app.route("/github_callback")
def github_callback():
    """
    After the user is authenticated in GitHub, GitHub will redirect to this route, and the
    metadata editor authentication will be finalised on the server.
    """

    def fetch_access_token(args):
        """
        Get the temporary code from the given args and use it to fetch a GitHub App access token
        for the configured client.
        """
        temporary_code = args.get("code")
        params = {
            "client_id": app.config["GITHUB_CLIENT_ID"],
            "client_secret": app.config["GITHUB_CLIENT_SECRET"],
            "code": temporary_code,
            "state": app.config["GITHUB_APP_STATE"],
            "redirect_uri": "{}/github_callback".format(app.config["FLASK_HOST"]),
        }

        try:
            response = github_authorize_token(params)
        except requests.HTTPError as e:
            logger.error(e)
            return None

        content = parse_qs(response.text)
        access_token = content.get("access_token")
        if not access_token:
            logger.error("Could not retrieve access token")
            return None
        access_token = access_token[0]

        token_type = content.get("token_type")
        if not token_type:
            logger.error("No token type returned")
            return None
        token_type = token_type[0]
        if token_type.casefold() != "bearer":
            logger.error(f"Unexpected token type retrieved: {token_type}")
            return None

        return access_token

    if request.args.get("state") != app.config["GITHUB_APP_STATE"]:
        logger.error(
            "Received wrong state. Aborting authorization due to possible CSRF attack."
        )
        return redirect("/logged_out")

    access_token = fetch_access_token(request.args)
    next_url = request.args.get("next") or url_for("index")
    if access_token is None:
        # If we don't receive a token just redirect; an error message should have been written to
        # the log in the fetch_access_token() function above.
        return redirect(next_url)

    # Check to see if we already have the user corresponding to this access token in the db, and add
    # her if we don't:
    user = User.query.filter_by(github_access_token=access_token).first()
    if user is None:
        user = User(access_token)
        db_session.add(user)

    # Add the user to the global application context:
    g.user = user

    # Get some other useful information about the user:
    github_user = github_call("GET", "/user")
    g.user.github_id = github_user["id"]
    g.user.github_login = github_user["login"]

    db_session.commit()

    # Add the user's id to the session and then redirect to the requested URL:
    session["user_id"] = user.id
    return redirect(next_url)


@app.route("/login")
def login():
    """
    Authenticate a user. For the authentication workflow, see:
    https://docs.github.com/en/free-pro-team@latest/developers/apps/identifying-and-authorizing-users-for-github-apps
    """
    # If the session already contains a user id, just get rid of it and re-authenticate. This could
    # happen, for example, if the users db gets deleted but the user's browser session still has
    # the user's id in it.
    if session.get("user_id") is not None:
        session.pop("user_id")

    params = {
        "client_id": app.config["GITHUB_CLIENT_ID"],
        "state": app.config["GITHUB_APP_STATE"],
        "redirect_uri": "{}/github_callback".format(app.config["FLASK_HOST"]),
    }
    try:
        response = github_authorize(params)
        return redirect(response.url)
    except requests.HTTPError as e:
        logger.error(e)
        return redirect(url_for("logged_out"))


@app.route("/logged_out")
def logged_out():
    """
    Displays the page to be shown to logged out users.
    """
    return render_template("logged_out.jinja2")


def verify_logged_in(fn):
    """
    Decorator used to make sure that the user is logged in
    """

    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        # If the user is not logged in, then redirect him to the "logged out" page:
        if not g.user:
            return redirect(url_for("logged_out"))
        return fn(*args, **kwargs)

    return wrapped


@app.route("/logout")
@verify_logged_in
def logout():
    """
    De-authenticate the user
    """
    # Simply pop the user id from the session cookie, which will be enough to signal to the server
    # that the user is not authenticated.
    session.pop("user_id", None)
    return redirect(url_for("logged_out"))


@app.route("/")
@verify_logged_in
def index():
    """
    Renders the index page of the application
    """
    # Get all of the available config files to edit:
    purl_configs = github_call(
        "GET",
        f'repos/{app.config["GITHUB_ORG"]}/{editor_types["purl"]["repo"]}/'
        f'contents/{editor_types["purl"]["dir"]}',
    )
    if not purl_configs:
        raise Exception("Could not get contents of the purl config directory")

    # Get all of the available registry config files to edit:
    registry_configs = github_call(
        "GET",
        f'repos/{app.config["GITHUB_ORG"]}/{editor_types["registry"]["repo"]}/'
        f'contents/{editor_types["registry"]["dir"]}',
    )
    if not registry_configs:
        raise Exception("Could not get contents of the registry config directory")

    # Add the title, url and description for each config to the records that will be rendered.
    # This information is found in the ontology metadata.
    configs = []
    for purl_config in purl_configs:
        config_id = purl_config["name"].casefold().replace(app.config["YAML_EXT"], "")
        # We skip the OBO idspace:
        if config_id != "obo":
            config_title = [o["title"] for o in ontology_md if o["id"] == config_id]
            config_title = config_title.pop() if config_title else ""
            config_description = [
                o["description"]
                for o in ontology_md
                if o["id"] == config_id and "description" in o
            ]
            config_description = config_description.pop() if config_description else ""
            if registry_configs:
                registries_for_idspace = [
                    x
                    for x in registry_configs
                    if x["name"] == config_id + app.config["MARKDOWN_EXT"]
                ]

            configs.append(
                {
                    "id": config_id,
                    "purl_filename": purl_config["name"],
                    "registry_filename": registries_for_idspace[0]["name"]
                    if len(registries_for_idspace) > 0
                    else None,
                    "title": config_title,
                    "description": config_description,
                }
            )

    for registry_config in registry_configs:
        config_id = (
            registry_config["name"].casefold().replace(app.config["MARKDOWN_EXT"], "")
        )
        if config_id not in [c["id"] for c in configs]:
            config_title = [o["title"] for o in ontology_md if o["id"] == config_id]
            config_title = config_title.pop() if config_title else ""
            config_description = [
                o["description"]
                for o in ontology_md
                if o["id"] == config_id and "description" in o
            ]
            config_description = config_description.pop() if config_description else ""
            configs.append(
                {
                    "id": config_id,
                    "purl_filename": None,
                    "registry_filename": registry_config["name"],
                    "title": config_title,
                    "description": config_description,
                }
            )

    return render_template("index.jinja2", configs=configs, login=g.user.github_login)


@app.route("/<path:path>")
@verify_logged_in
def send_editor_page(path):
    """
    Route for serving up static files, including third party libraries.
    """
    return send_from_directory(pwd, path, as_attachment=False)


@app.route("/edit_new", methods=["POST"])
@verify_logged_in
def edit_new():
    """
    Handles a POST request to start an editing session for a new configuration file. The parameters
    expected in the POST body are:
    issueNumber: the original GitHub issue associated with this new registration, if it exists
    projectId: the ID associated with the new project configuration (e.g. 'AGRO')
    githubOrg: the github organisation for the project
    githubRepo: the github repository within the github organisation.
    editor_type: whether to create REGISTRY or PURL configuration
    addIssueLink: the issue link associated with the registry registration request, for PURL request
    """
    logger.debug(f"Got edit_new request {request.form}")

    issueNumber = request.form.get("issueNumber")
    project_id = request.form.get("projectId")
    github_org = request.form.get("githubOrg")
    github_repo = request.form.get("githubRepo")
    editor_type = request.form.get("editor_type")
    addIssueLink = request.form.get("addIssueLink")

    if issueNumber is None and any(
        [item is None for item in [project_id, github_org, github_repo]]
    ):
        return Response("Malformed POST request", status=400)

    logger.debug(f"Got editor type: {editor_type}")
    gHubRegex = r"https?://github\.com/([^/]*)/([^/]*)/?"
    issueDetails = None
    if issueNumber:
        # Retrieve all the information from the issue
        # GET /repos/:owner/:repo/issues/:issue_number
        issueData = github_call(
            "GET",
            f'repos/{app.config["GITHUB_ORG"]}/'
            f'{editor_types["registry"]["repo"]}/'
            f"issues/{issueNumber}",
        )["body"]
        logger.debug(f"Got issue body {issueData}")
        try:
            issueDetails = yaml.load(issueData)
            # Remove keys not needed for the registry metadata
            del issueDetails["related_ontologies"]
            del issueDetails["intended_use"]
            del issueDetails["data_source"]
            del issueDetails["remarks"]

            ontologyLocation = issueDetails["homepage"]
            project_id = issueDetails["id"]
            githuburl = re.match(gHubRegex, ontologyLocation)
            if githuburl and github_org is None and github_repo is None:
                github_org = githuburl.group(1)
                github_repo = githuburl.group(2)
                logger.debug(f"Got github details: {github_org}, {github_repo}")
        except (YAMLError, TypeError) as err:
            # Try to parse it from the GitHub issue template format
            if "## Ontology title" in issueData:
                issueDetails = {}
                issueDetails["description"] = ""
                fields = [f.strip() for f in issueData.split("##")]
                for fieldString in fields:
                    if fieldString.startswith("Ontology title"):
                        issueDetails["title"] = fieldString.replace(
                            "Ontology title", ""
                        ).strip()
                    elif fieldString.startswith("Requested ID space"):
                        project_id = fieldString.replace("Requested ID space", "").strip()
                        issueDetails["id"] = project_id
                    elif fieldString.startswith("Ontology location"):
                        issueDetails["homepage"] = fieldString.replace(
                            "Ontology location", ""
                        ).strip()
                        logger.debug(
                            f"Looking for github details in {issueDetails['homepage']}"
                        )
                        githuburl = re.match(gHubRegex, issueDetails["homepage"])
                        if githuburl:
                            logger.debug(f"Match object {githuburl}")
                            github_org = githuburl.group(1)
                            github_repo = githuburl.group(2)
                            logger.debug(
                                f"Got github details: '{github_org}', '{github_repo}'"
                            )
                    elif fieldString.startswith("Contact person"):
                        lines = fieldString.replace("Contact person", "").split("\n")
                        for line in lines:
                            if line.strip().startswith("Name:"):
                                name = line.replace("Name:", "").strip()
                            elif line.strip().startswith("Email address:"):
                                email = line.replace("Email address:", "").strip()
                            elif line.strip().startswith("GitHub username:"):
                                github = line.replace("GitHub username:", "").strip()
                        contact = {"label": name, "email": email, "github": github}
                        issueDetails["contact"] = contact
                    elif fieldString.startswith("Issue tracker"):
                        issueDetails["tracker"] = fieldString.replace(
                            "Issue tracker", ""
                        ).strip()
                    elif fieldString.startswith(
                        "What domain is the ontology intended to cover?"
                    ):
                        issueDetails["domain"] = fieldString.replace(
                            "What domain is the ontology intended to cover?", ""
                        ).strip()
                    elif fieldString.startswith("Ontology license"):
                        if "[x] CC0" in fieldString:
                            url = "http://creativecommons.org/publicdomain/zero/1.0/"
                            label = "CC-0"
                        elif "[x] CC-BY" in fieldString:
                            url = "http://creativecommons.org/licenses/by/4.0/"
                            label = "CC-BY 4.0"
                        elif "[x] Other" in fieldString:
                            url = None
                            label = fieldString[
                                fieldString.index("[x] Other") + 10 : len(fieldString)
                            ].strip()
                        licenseInfo = {"url": url, "label": label}
                        issueDetails["license"] = licenseInfo

                logger.debug(
                    f"Got issue details from parsed issue template: {issueDetails}"
                )

            else:  # Can't parse this issue with any strategy, something has gone wrong.
                issues = {}
                issue_list = github_call(
                    "GET",
                    f'repos/{app.config["GITHUB_ORG"]}/{editor_types["registry"]["repo"]}/issues',
                    params={"state": "open", "labels": "new ontology"},
                )
                for issue in issue_list:
                    number = issue["number"]
                    title = issue["title"]
                    logger.debug(f"Got issue: {number}, {title}")
                    issues[number] = title
                error_message = format(err)
                return render_template(
                    "prepare_new_config.jinja2",
                    login=g.user.github_login,
                    project_id=project_id,
                    github_org=github_org,
                    github_repo=github_repo,
                    error_message=f"Not able to parse metadata in the issue {issueNumber}, "
                    f"due to: <i>{error_message}</i>. Please "
                    f"<a href='http://github.com/{app.config['GITHUB_ORG']}/"
                    f"{editor_types['registry']['repo']}/issues/{issueNumber}' "
                    f"target = '_new'>visit the issue</a> to correct the YAML metadata, "
                    f"or alternatively enter the required GitHub information below.",
                    issueList=issues,
                    issueNumber=issueNumber,
                )

    if editor_type is None:  # First step
        try:
            github_call("GET", f"repos/{github_org}/{github_repo}")
        except requests.HTTPError:
            # Get the issuse list again
            issues = {}
            issue_list = github_call(
                "GET",
                f'repos/{app.config["GITHUB_ORG"]}/{editor_types["registry"]["repo"]}/issues',
                params={"state": "open", "labels": "new ontology"},
            )
            for issue in issue_list:
                number = issue["number"]
                title = issue["title"]
                logger.debug(f"Got issue: {number}, {title}")
                issues[number] = title

            return render_template(
                "prepare_new_config.jinja2",
                login=g.user.github_login,
                project_id=project_id,
                github_org=github_org,
                github_repo=github_repo,
                error_message=f"Unable to create initial ontology metadata, as "
                f"the GitHub repository at {github_org}/{github_repo} does not exist. "
                f" Please enter the GitHub details for your project.",
                issueList=issues,
                issueNumber=issueNumber,
            )
        # If issueDetails have not been loaded, populate an empty template
        if issueDetails is None:
            # Generate an empty template
            issueDetails = {}
            issueDetails["title"] = ""
            issueDetails["id"] = project_id
            issueDetails["homepage"] = f"https://github.org/{github_org}/{github_repo}/"
            issueDetails[
                "tracker"
            ] = f"https://github.org/{github_org}/{github_repo}/issues"
            issueDetails["contact"] = {
                "label": "",
                "email": "",
                "github": g.user.github_login,
            }
            issueDetails["license"] = {"url": "", "label": ""}
            issueDetails["description"] = ""
            issueDetails["domain"] = ""

        # Generate text for initial registry config
        stringio = StringIO()
        yaml.dump(
            {
                "layout": "ontology_detail",
                **issueDetails,
                "products": [{"id": f"{project_id.lower()}.owl"}],
                "activity_status": "active",
            },
            stringio,
        )
        registryYamlText = stringio.getvalue()
        registryYamlText = app.config["NEW_PROJECT_REGISTRY_TEMPLATE"].format(
            idspace_lower=project_id.lower(),
            yaml_registry_details=registryYamlText,
            description=issueDetails["description"],
        )
        logger.debug(f"Got registry yaml text: {registryYamlText}")

        return render_template(
            "editor.jinja2",
            filename=f'{project_id.lower()}{app.config["MARKDOWN_EXT"]}',
            editor_type="registry",
            existing=False,
            yaml=registryYamlText,
            issueNumber=issueNumber,
            login=g.user.github_login,
            schema_file=json.dumps(registry_schema),
        )
    elif editor_type == "purl":
        # Generate some text to populate the editor initially with,
        # based on the new project template,
        # and then inject it into the jinja2 template for the metadata editor:
        purlYamlText = app.config["NEW_PROJECT_PURL_TEMPLATE"].format(
            idspace_upper=project_id.upper(),
            idspace_lower=project_id.casefold(),
            org=github_org,
            git=github_repo,
        )

        return render_template(
            "editor.jinja2",
            filename=f'{project_id.lower()}{app.config["YAML_EXT"]}',
            editor_type="purl",
            existing=False,
            yaml=purlYamlText,
            addIssueLink=addIssueLink,
            login=g.user.github_login,
            schema_file=json.dumps(purl_schema),
        )
    else:
        return Response("Malformed POST request, unknown editor type", status=400)


@app.route("/prepare_new", methods=["GET"])
@verify_logged_in
def prepare_new():
    """
    Handles a request to add a prepare project configuration. This is the first step in a two-step
    process. This endpoint generates a form to request information about the new project from the
    user. Once the form is submitted a request is sent to begin editing the new config.
    """

    issues = {}
    issue_list = github_call(
        "GET",
        f'repos/{app.config["GITHUB_ORG"]}/{editor_types["registry"]["repo"]}/issues',
        params={"state": "open", "labels": "new ontology"},
    )
    for issue in issue_list:
        number = issue["number"]
        title = issue["title"]
        logger.debug(f"Got issue: {number}, {title}")
        issues[number] = title

    return render_template(
        "prepare_new_config.jinja2", login=g.user.github_login, issueList=issues
    )


@app.route("/foundry_reg", methods=["GET"])
@verify_logged_in
def prepare_foundry():
    """
    Handles a request to create a new OBO Foundry ontology registration.
    """
    github_user = github_call("GET", "/user")

    github_name = github_user["name"]
    github_email = github_user["email"] if "email" in github_user else None

    return render_template(
        "new_foundry_reg.jinja2",
        login=g.user.github_login,
        contactPerson=github_name,
        contactGitHub=g.user.github_login,
        contactEmail=github_email,
    )


@app.route("/foundry_reg", methods=["POST"])
@verify_logged_in
def new_foundry():
    """
    Handles a POST request to request a new Foundry ontology registration. The parameters
    expected in the POST body are:
    ontologyTitle
    idSpace
    ontoLoc
    issueTracker
    contactPerson
    contactEmail
    contactGitHub
    ontoLicense
    domain
    relatedOntos
    intendedUse
    dataSource
    remarks
    """
    ontologyTitle = request.form.get("ontologyTitle")
    idSpace = request.form.get("idSpace")
    ontoLoc = request.form.get("ontoLoc")
    contactPerson = request.form.get("contactPerson")
    contactEmail = request.form.get("contactEmail")
    contactGitHub = request.form.get("contactGitHub")
    issueTracker = request.form.get("issueTracker")
    ontoLicense = request.form.get("ontoLicense")
    description = request.form.get("description")
    domain = request.form.get("domain")
    relatedOntos = request.form.get("relatedOntos")
    intendedUse = request.form.get("intendedUse")
    dataSource = request.form.get("dataSource")
    remarks = request.form.get("remarks")

    if any(
        [
            item is None
            for item in [
                ontologyTitle,
                idSpace,
                ontoLoc,
                contactPerson,
                contactEmail,
                contactGitHub,
                issueTracker,
                ontoLicense,
                description,
                domain,
                relatedOntos,
                intendedUse,
                dataSource,
            ]
        ]
    ):
        return Response("Malformed POST request", status=400)

    # Validate the requested ID space is unique across the existing registry
    registry_configs = github_call(
        "GET",
        f'repos/{app.config["GITHUB_ORG"]}/{editor_types["registry"]["repo"]}/'
        f'contents/{editor_types["registry"]["dir"]}',
    )
    if not registry_configs:
        raise Exception("Could not get contents of the registry config directory")
    registry_config_ids = [
        rc["name"].casefold().replace(app.config["MARKDOWN_EXT"], "")
        for rc in registry_configs
    ]
    if idSpace.casefold() in registry_config_ids:
        resultType = "failure"
        logger.error(f"Non-unique ID requested: {idSpace}")
        return render_template(
            "new_foundry_reg.jinja2",
            login=g.user.github_login,
            resultType=resultType,
            errorMessage=f"The ID space '{idSpace}' is already in use. Please try "
            f"a different option. ",
            ontologyTitle=ontologyTitle,
            idSpace=idSpace,
            ontoLoc=ontoLoc,
            issueTracker=issueTracker,
            contactPerson=contactPerson,
            contactEmail=contactEmail,
            contactGitHub=contactGitHub,
            ontoLicense=ontoLicense,
            description=description,
            domain=domain,
            relatedOntos=relatedOntos,
            intendedUse=intendedUse,
            dataSource=dataSource,
            remarks=remarks,
        )
    # get license URL
    if ontoLicense == "CC-0":
        licenseURL = "https://creativecommons.org/publicdomain/zero/1.0/"
    elif ontoLicense == "CC-BY":
        licenseURL = "https://creativecommons.org/licenses/by/4.0/"
    else:
        licenseURL = ""
    issueDict = {}
    issueDict["title"] = ontologyTitle
    issueDict["id"] = idSpace
    issueDict["homepage"] = ontoLoc
    issueDict["tracker"] = issueTracker
    issueDict["contact"] = {
        "label": contactPerson,
        "email": contactEmail,
        "github": contactGitHub,
    }
    issueDict["license"] = {"url": licenseURL, "label": ontoLicense}
    issueDict["description"] = description
    issueDict["domain"] = domain
    issueDict["related_ontologies"] = relatedOntos
    issueDict["intended_use"] = intendedUse
    issueDict["data_source"] = dataSource
    issueDict["remarks"] = remarks

    stringio = StringIO()
    yaml.dump(issueDict, stringio)
    issueBody = stringio.getvalue()
    issueTitle = f"New Ontology Request: {ontologyTitle}"

    url = app.config["REGISTRY_REQUEST"]
    logger.debug(f"About to try to create GitHub new ontology request issue at {url}")

    # Create our issue
    issue = {"title": issueTitle, "body": issueBody, "labels": ["new ontology"]}
    # Add the issue to our repository
    try:
        response = github_call("POST", url, issue)
        if response:
            logger.debug(f"Successfully created issue {issueTitle}, response: {response}")
            resultType = "success"
        else:
            resultType = "failure"
            logger.error(f"Could not create issue {issueTitle}")
            return render_template(
                "new_foundry_reg.jinja2",
                login=g.user.github_login,
                resultType=resultType,
                errorMessage="An unknown error occurred, there was no response.",
                ontologyTitle=ontologyTitle,
                idSpace=idSpace,
                ontoLoc=ontoLoc,
                issueTracker=issueTracker,
                contactPerson=contactPerson,
                contactEmail=contactEmail,
                contactGitHub=contactGitHub,
                ontoLicense=ontoLicense,
                description=description,
                domain=domain,
                relatedOntos=relatedOntos,
                intendedUse=intendedUse,
                dataSource=dataSource,
                remarks=remarks,
            )
    except requests.HTTPError as err:
        resultType = "failure"
        print(f"An unexpected error occurred: {err},{err.response.json()['message']}")
        return render_template(
            "new_foundry_reg.jinja2",
            login=g.user.github_login,
            resultType=resultType,
            errorMessage=err.response.json()["message"],
            ontologyTitle=ontologyTitle,
            idSpace=idSpace,
            ontoLoc=ontoLoc,
            issueTracker=issueTracker,
            contactPerson=contactPerson,
            contactEmail=contactEmail,
            contactGitHub=contactGitHub,
            ontoLicense=ontoLicense,
            description=description,
            domain=domain,
            relatedOntos=relatedOntos,
            intendedUse=intendedUse,
            dataSource=dataSource,
            remarks=remarks,
        )

    emailDraft = app.config["NEW_ONTOLOGY_EMAIL_TEMPLATE"].format(
        idSpace=idSpace,
        ontologyTitle=ontologyTitle,
        ontoLoc=ontoLoc,
        domain=domain,
        issueLink=response["html_url"],
        contactPerson=contactPerson,
    )

    return render_template(
        "new_foundry_reg.jinja2",
        login=g.user.github_login,
        resultType=resultType,
        ontologyTitle=ontologyTitle,
        idSpace=idSpace,
        emailDraft=emailDraft,
        issueURL=response["html_url"],
    )


@app.route("/edit/<editor_type>/<filename>")
@verify_logged_in
def edit_config(editor_type, filename):
    """
    Get the contents of the given path (purl or registry) from the github repository
    and render it in the editor using the jinja2 template for the metadata editor
    """
    if editor_type not in editor_types.keys():
        raise Exception(f"Unknown metadata type: {editor_type}")

    config_file = github_call(
        "GET",
        f'repos/{app.config["GITHUB_ORG"]}/{editor_types[editor_type]["repo"]}/'
        f'contents/{editor_types[editor_type]["dir"]}/{filename}',
    )
    if not config_file:
        raise Exception(f"Could not get the contents of: {filename}")

    schema_file = purl_schema if editor_type == "purl" else registry_schema

    decodedBytes = base64.b64decode(config_file["content"])
    decodedStr = str(decodedBytes, "utf-8")
    return render_template(
        "editor.jinja2",
        existing=True,
        editor_type=editor_type,
        yaml=decodedStr,
        filename=config_file["name"],
        login=g.user.github_login,
        schema_file=json.dumps(schema_file),
    )


@app.route("/validate", methods=["POST"])
@verify_logged_in
def validate():
    """
    Handles a request to validate a block of OBO PURL YAML code. If the code is valid, returns a
    HTTP status of 200. Otherwise if there is either a YAML parsing error or a violation of the
    constraints specified in the JSON schema, then a 400 is returned along with a JSON object
    indicating a summary of the error, the line number of the error (if available), and the detailed
    output of the error.
    """

    def find_schema_error_line(keys, yaml_source):
        logger.debug(f"Trying to determine line number for path {keys}")
        line_number = -1
        if err.validator == "additionalProperties":
            logger.debug("Got additional properties error")
            m = err.message
            key = m[
                m.index("'") + 1 : m.rindex("'")
            ]  # get the added key name; this is hacky
            keys.append(key)
        if len(keys) > 0:
            subset = yaml_source
            while len(keys) > 1:
                subset = subset[
                    keys.pop(0)
                ]  # follow the path, stopping with one key left
            if keys[0] in subset.lc.data:
                pos = subset.lc.data[keys[0]]  # get ruamel.yaml's line-column information
                line_number = pos[0] + 1
                logger.debug(f"at line {pos[0] + 1}, column {pos[1] + 1}")
        return line_number

    if request.form.get("code") is None:
        return Response("Malformed POST request", status=400)

    try:
        code = request.form["code"]
        editor_type = request.form["editor_type"]
        if editor_type == "purl":
            s = purl_schema
            yaml_source = yaml.load(code)
            jsonschema.validate(yaml_source, purl_schema)
        elif editor_type == "registry":
            results = {}
            split_pattern = "---"
            code_sections = re.split(split_pattern, code)
            if len(code_sections) < 2:
                logger.debug(f"Not enough sub-sections in registry config code {code}")
                return Response(
                    f"Not enough sub-sections in registry config "
                    f"file code: {len(code_sections)}",
                    status=400,
                )
            yaml_code = code_sections[1]
            yaml_source = yaml.load(yaml_code)
            s = registry_schema
            try:
                jsonschema.validate(yaml_source, s)
            except jsonschema.exceptions.ValidationError as err:
                logger.debug(
                    f"JSON validation error in {list(err.absolute_schema_path)} "
                    f":: {list(err.relative_schema_path)} "
                )
                title = list(err.absolute_schema_path)[0]  # first entry
                if title == "required":
                    field_names = re.findall(r"\'(.*?)\'", err.message)  # Get which field
                    if len(field_names) > 0:
                        title = field_names[0]
                if title == "properties":
                    title = list(err.absolute_schema_path)[
                        1
                    ]  # Which property? Second entry
                logger.debug(f"Got error title {title}")
                # What is the level of this error?
                if "level" in err.schema:
                    result_type = err.schema["level"]
                    logger.debug(f"Got error level: {result_type}")
                else:
                    logger.debug(f"No error level found in {err.schema}")
                    result_type = "warning"

                if "is_obsolete" in yaml_source and yaml_source["is_obsolete"]:
                    logger.debug(
                        "Demoting schema error level for obsolete registry entry"
                    )
                    if result_type == "error":
                        result_type = "warning"
                    elif result_type == "warning":
                        result_type = "info"

                if result_type not in results:
                    results[result_type] = {}

                logger.debug(err.message)
                line_number = find_schema_error_line(list(err.absolute_path), yaml_source)

                if result_type == "error":
                    status = 400
                else:
                    status = 200
                error_summary = err.message
                if err.absolute_schema_path:
                    err_descr = err.schema.get("description")
                    if err_descr:
                        error_summary = f"{err.message} ({err_descr})"
                response = (
                    jsonify(
                        {
                            "result_type": result_type,
                            "summary": format(error_summary),
                            "line_number": line_number,
                            "details": format(err),
                        }
                    ),
                    status,
                )
                results[result_type][title] = response
            logger.debug(f"Got schema validation results: {results}")
            for result_type in ["error", "warning", "info"]:
                if (
                    result_type in results
                    and results[result_type] is not None
                    and len(results[result_type].values()) > 0
                ):
                    return next(iter(results[result_type].values()))
        else:
            return Response(f"Unknown editor type: {editor_type}", status=400)

    except (DuplicateKeyError, YAMLError, TypeError) as err:
        line_number = -1
        if hasattr(err, "problem_mark"):
            mark = err.problem_mark
            logger.debug(f"Error has position: ({mark.line+1}:{mark.column+1})")
            line_number = mark.line + 1
        else:
            logger.debug(f"Error {err} has no associated line number information.")
        return (
            jsonify(
                {
                    "result_type": "error",
                    "summary": "YAML parsing error",
                    "line_number": line_number,
                    "details": format(err),
                }
            ),
            400,
        )
    except jsonschema.exceptions.ValidationError as err:
        result_type = "error"
        logger.debug(err.message)
        line_number = find_schema_error_line(list(err.absolute_path), yaml_source)
        status = 400
        error_summary = err.message
        if err.absolute_schema_path:
            err_descr = err.schema.get("description")
            if err_descr:
                error_summary = f"{err.message} ({err_descr})"
        return (
            jsonify(
                {
                    "result_type": result_type,
                    "summary": format(error_summary),
                    "line_number": line_number,
                    "details": format(err),
                }
            ),
            status,
        )

    return Response(status=200)


def get_file_sha(repo, rep_dir, filename):
    """
    Get the sha of the given filename from the given github repository
    """
    response = github_call("GET", f"repos/{repo}/contents/{rep_dir}/{filename}")
    if not response or "sha" not in response:
        raise Exception(
            f"Unable to get the current SHA value for {filename} in {repo}/{rep_dir}"
        )
    return response["sha"]


def get_master_sha(repo):
    """
    Get the sha for the HEAD of the master branch in the given github repository
    """
    response = github_call("GET", f"repos/{repo}/git/ref/heads/master")
    if not response or "object" not in response or "sha" not in response["object"]:
        raise Exception(f"Unable to get SHA for HEAD of master in {repo}")
    return response["object"]["sha"]


def create_branch(repo, filename, master_sha):
    """
    Create a new branch, from master (identified by its sha), based on the given filename
    in the given repository.
    """
    # Generate the branch name:
    branch = (
        f"{g.user.github_login}_{filename.replace(app.config['YAML_EXT'], '').upper()}"
        f"_{datetime.utcnow().strftime('%Y-%m-%d_%H%M%S')}"
    )

    response = github_call(
        "POST",
        f"repos/{repo}/git/refs",
        params={"ref": f"refs/heads/{branch}", "sha": master_sha},
    )
    if not response:
        raise Exception(f"Unable to create new branch {branch} in {repo}")

    return branch


def commit_to_branch(repo, branch, code, rep_dir, filename, commit_msg, file_sha=None):
    """
    Commit the given code to the given branch in the given repo, using the given commit message.
    If the optional file_sha parameter is specified (because this commit is for an existing file)
    then include it in the request to github.
    """
    data = {
        "message": commit_msg,
        "content": base64.b64encode(code.encode("utf-8")).decode(),
        "branch": branch,
    }

    if file_sha:
        data["sha"] = file_sha

    response = github_call(
        "PUT", f"repos/{repo}/contents/{rep_dir}/{filename}", params=data
    )
    if not response:
        raise Exception(
            f"Unable to commit addition of {filename} to branch {branch} in {repo}"
        )


def create_pr(repo, branch, commit_msg, draft, long_msg=""):
    """
    Create a pull request for the given branch in the given repository in github
    """
    data = {"title": commit_msg, "head": branch, "base": "master", "body": long_msg}
    if draft == "true":
        data["draft"] = True
    logger.debug(f"PR data={data}")
    response = github_call("POST", f"repos/{repo}/pulls", params=data)
    if not response:
        raise Exception(f"Unable to create PR for branch {branch} in {repo}")

    return response


@app.route("/add_config", methods=["POST"])
@verify_logged_in
def add_config():
    """
    Route for initiating a pull request to add a config file to the repository
    """
    filename = request.form.get("filename")
    code = request.form.get("code")
    commit_msg = request.form.get("commit_msg")
    editor_type = request.form.get("editor_type")
    draft = request.form.get("draft")
    long_msg = request.form.get("long_msg")
    if any([item is None for item in [filename, commit_msg, code, editor_type]]):
        return Response("Malformed POST request", status=400)

    repo = f'{app.config["GITHUB_ORG"]}/{editor_types[editor_type]["repo"]}'

    try:
        master_sha = get_master_sha(repo)
        new_branch = create_branch(repo, filename, master_sha)
        logger.info(f"Created a new branch: {new_branch} in {repo}")
        commit_to_branch(
            repo,
            new_branch,
            code,
            editor_types[editor_type]["dir"],
            filename,
            commit_msg,
        )
        logger.info(f"Committed addition of {filename} to branch {new_branch} in {repo}")
        pr_info = create_pr(repo, new_branch, commit_msg, draft, long_msg)
        logger.info(f"Created a PR for branch {new_branch} in {repo}")
    except Exception as e:
        return Response(format(e), status=400)

    # We return github's response to the caller, which contains info on the PR (among other things,
    # a URL to use to access it):
    return jsonify({"pr_info": pr_info})


@app.route("/update_config", methods=["POST"])
@verify_logged_in
def update_config():
    """
    Route for initiating a pull request to update a PURL config file in the github repository.
    """
    filename = request.form.get("filename")
    code = request.form.get("code")
    commit_msg = request.form.get("commit_msg")
    draft = request.form.get("draft")
    editor_type = request.form.get("editor_type")
    long_msg = request.form.get("long_msg")

    if any([item is None for item in [filename, commit_msg, code, editor_type]]):
        return Response("Malformed POST request", status=400)

    # Get the contents of the current version of the file:
    curr_contents = github_call(
        "GET",
        f'repos/{app.config["GITHUB_ORG"]}/{editor_types[editor_type]["repo"]}/'
        f'contents/{editor_types[editor_type]["dir"]}/{filename}',
    )
    if not curr_contents:
        raise Exception(f"Could not get the contents of: {filename}")

    decodedBytes = base64.b64decode(curr_contents["content"])
    decodedStr = str(decodedBytes, "utf-8")

    # Verify that the contents to be committed differ from the current contents, return a 422
    # if they are the same:
    if decodedStr == code:
        return Response(
            "Update request refused: The submitted configuration is identical to the "
            "currently saved version.",
            status=422,
        )

    repo = f'{app.config["GITHUB_ORG"]}/{editor_types[editor_type]["repo"]}'

    try:
        file_sha = get_file_sha(repo, editor_types[editor_type]["dir"], filename)
        master_sha = get_master_sha(repo)
        new_branch = create_branch(repo, filename, master_sha)
        logger.info(f"Created a new branch: {new_branch} in {repo}")
        commit_to_branch(
            repo,
            new_branch,
            code,
            editor_types[editor_type]["dir"],
            filename,
            commit_msg,
            file_sha,
        )
        logger.info(f"Committed update of {filename} to branch {new_branch} in {repo}")
        pr_info = create_pr(repo, new_branch, commit_msg, draft, long_msg)
        logger.info(f"Created a PR for branch {new_branch} in {repo}")
    except Exception as e:
        return Response(format(e), status=400)

    # We return github's response to the caller, which contains info on the PR (among other things,
    # a URL to use to access it):
    return jsonify({"pr_info": pr_info})


def init_db():
    """
    Initialise the users database
    """
    Base.metadata.create_all(bind=engine)


# Call the function initialising the users db:
init_db()


if __name__ == "__main__":
    app.run(
        host=app.config["FLASK_HOST"],
        debug=True if app.config["LOG_LEVEL"] == "DEBUG" else False,
    )
