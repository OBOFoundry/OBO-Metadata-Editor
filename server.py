#!/usr/bin/env python3

import base64
import functools
import json
import jsonschema
import logging
import os
import re
import yaml

from datetime import datetime
from flask import Flask, jsonify, render_template, request, Response, g, send_from_directory, \
  session, redirect, url_for
from flask_github import GitHub, GitHubError
from gevent.pywsgi import WSGIServer
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from urllib.request import urlopen

# To run in development mode, do:
# export FLASK_APP=server.py
# export FLASK_DEBUG=1 (optional)
# python3 -m flask run

# Note that the following environment variables must be set:
# GITHUB_CLIENT_ID
# GITHUB_CLIENT_SECRET
# FLASK_SECRET_KEY

# Setup the webapp:
app = Flask(__name__)
app.config.from_object('config')
app.secret_key = app.config['FLASK_SECRET_KEY']

# Initialize the logger:
logging.basicConfig(format=app.config['LOGGING_CONFIG'])
logger = logging.getLogger(__name__)
logger.setLevel(app.config['LOG_LEVEL'])

# The filesystem directory where this script is running from:
pwd = app.config['PWD']

# Load the validation schema:
schema = json.load(open(app.config['SCHEMAFILE']))

# Setup github-flask through which we'll communicate with the GitHub API:
github = GitHub(app)

# Setup sqlalchemy to manage the database of logged in users:
engine = create_engine(app.config['DATABASE_URI'])
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()


# Retrieve the ontology metadata:
try:
  ontology_md = urlopen(app.config['ONTOLOGY_METADATA_URL'])
  if ontology_md.getcode() == 200:
    ontology_md = yaml.load(ontology_md.read(), Loader=yaml.SafeLoader)['ontologies']
except Exception as e:
  logger.error("Could not retrieve ontology metadata: {}".format(e))
  ontology_md = {}


class User(Base):
  """
  Saved information for users that have been authenticated to the purl-editor. Note that this table
  preserves historical data (user records are not deleted when a user logs out)
  """
  __tablename__ = 'users'

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
  if 'user_id' in session:
    g.user = User.query.get(session['user_id'])


@app.after_request
def after_request(response):
  """
  Called at the end of every request.
  """
  # Clean up the database session:
  db_session.remove()
  return response


@github.access_token_getter
def token_getter():
  """
  Called automatically by github_flask to retrieve the token for the user belonging to
  the global application context.
  """
  user = g.user
  if user is not None:
    return user.github_access_token


@app.route('/github_callback')
@github.authorized_handler
def authorized(access_token):
  """
  After the user is authenticated in GitHub, GitHub will redirect to this route, and the
  purl-editor authentication will be finalised on the server.
  """
  next_url = request.args.get('next') or url_for('index')

  if access_token is None:
    logger.warn("No access token received. Redirecting to {}".format(next_url))
    return redirect(next_url)

  # If this check fails then there may have been an attempted CSRF attack:
  if request.args.get('state') != app.config['GITHUB_OAUTH_STATE']:
    logger.warn("Received unexpected request state; possible CSRF attack")
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
  github_user = github.get('/user')
  g.user.github_id = github_user['id']
  g.user.github_login = github_user['login']

  db_session.commit()

  # Add the user's id to the session and then redirect to the requested URL:
  session['user_id'] = user.id
  return redirect(next_url)


@app.route('/login')
def login():
  """
  Authenticate a user
  """
  # If the session already contains a user id, just get rid of it and re-authenticate. This could
  # happen, for example, if the users db gets deleted but the user's browser session still has
  # the user's id in it.
  if session.get('user_id') is not None:
    session.pop('user_id')
  return github.authorize(scope='repo', state=app.config.get('GITHUB_OAUTH_STATE'))


@app.route('/logged_out')
def logged_out():
  """
  Displays the page to be shown to logged out users.
  """
  return render_template('logged_out.jinja2')


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


@app.route('/logout')
@verify_logged_in
def logout():
  """
  De-authenticate the user
  """
  # Simply pop the user id from the session cookie, which will be enough to signal to the server
  # that the user is not authenticated.
  session.pop('user_id', None)
  return redirect(url_for('logged_out'))


@app.route('/')
@verify_logged_in
def index():
  """
  Renders the index page of the application
  """
  # Get all of the available config files to edit:
  full_configs = github.get('repos/{}/{}/contents/config'
                            .format(app.config['GITHUB_ORG'], app.config['GITHUB_REPO']))
  if not full_configs:
    raise Exception("Could not get contents of the config directory")

  # Add the title for each config to the records that will be rendered. The title is found in the
  # ontology metadata.
  configs = []
  for full_config in full_configs:
    config_id = full_config['name'].casefold().replace(".yml", "")
    # We skip the OBO idspace:
    if config_id != "obo":
      config_title = [o['title'] for o in ontology_md if o['id'] == config_id]
      config_title = config_title.pop() if config_title else ""
      configs.append(
        {'name': full_config['name'], 'path': full_config['path'], 'title': config_title})

  return render_template('index.jinja2', configs=configs, login=g.user.github_login)


@app.route('/<path:path>')
@verify_logged_in
def send_editor_page(path):
  """
  Route for serving up static files, including third party libraries.
  """
  return send_from_directory(pwd, path, as_attachment=False)


@app.route('/edit_new', methods=['POST'])
@verify_logged_in
def edit_new():
  """
  Handles a POST request to start an editing session for a new configuration file. The parameters
  expected in the POST body are:
  projectId: the ID associated with the new project configuration (e.g. 'AGRO')
  githubOrg: the github organisation for the project
  githubRepo: the github repository within the github organisation.
  """
  project_id = request.form.get('projectId')
  github_org = request.form.get('githubOrg')
  github_repo = request.form.get('githubRepo')
  if any([item is None for item in [project_id, github_org, github_repo]]):
    return Response("Malformed POST request", status=400)

  # Make sure that the requested github organisation/repository combination actually exists:
  try:
    github.get('repos/{}/{}'.format(github_org, github_repo))
  except GitHubError as e:
    return render_template('prepare_new_config.jinja2',
                           login=g.user.github_login,
                           project_id=project_id,
                           github_org=github_org,
                           github_repo=github_repo,
                           notfound='{}/{} does not exist'.format(github_org, github_repo))

  # Generate some text to populate the editor initially with, based on the new project template, and
  # then inject it into the jinja2 template for the purl-editor:
  yaml = app.config['NEW_PROJECT_TEMPLATE'].format(
    idspace_upper=project_id.upper(), idspace_lower=project_id.casefold(),
    org=github_org, git=github_repo)

  return render_template('purl_editor.jinja2',
                         filename='{}.yml'.format(project_id.lower()),
                         existing=False,
                         yaml=yaml,
                         login=g.user.github_login)


@app.route('/prepare_new', methods=['GET'])
@verify_logged_in
def prepare_new():
  """
  Handles a request to add a prepare project configuration. This is the first step in a two-step
  process. This endpoint generates a form to request information about the new project from the
  user. Once the form is submitted a request is sent to begin editing the new config.
  """
  return render_template('prepare_new_config.jinja2', login=g.user.github_login)


@app.route('/edit/<path:path>')
@verify_logged_in
def edit_config(path):
  """
  Get the contents of the given path from the github repository and render it in the
  editor using the jinja2 template for the purl-editor
  """
  config_file = github.get(
    'repos/{}/{}/contents/{}'.format(app.config['GITHUB_ORG'], app.config['GITHUB_REPO'], path))
  if not config_file:
    raise Exception("Could not get the contents of: {}".format(path))

  decodedBytes = base64.b64decode(config_file['content'])
  decodedStr = str(decodedBytes, "utf-8")
  return render_template('purl_editor.jinja2',
                         existing=True,
                         yaml=decodedStr,
                         filename=config_file['name'],
                         login=g.user.github_login)


@app.route('/validate', methods=['POST'])
@verify_logged_in
def validate():
  """
  Handles a request to validate a block of OBO PURL YAML code. If the code is valid, returns a
  HTTP status of 200. Otherwise if there is either a YAML parsing error or a violation of the
  constraints specified in the JSON schema, then a 400 is returned along with a JSON object
  indicating a summary of the error, the line number of the error (if available), and the detailed
  output of the error.
  """
  def get_error_start(code, start, block_label, item=-1):
    """
    Given some YAML code and a line to begin searching from within it, then if no item is specified
    this function returns the line number of the given block_label (a YAML directive of the form
    '(- )label:') is returned. If an item number n is specified, then the line number corresponding
    to the nth item within the block is returned instead (where items within a block in the form:
    - item 1
    - item 2
    - etc.)
    """
    logger.debug("Searching from line {line} for{item}block: '{block}'"
                 .format(line=start + 1,
                         item=' item #{} of '.format(item + 1) if item >= 0 else ' ',
                         block=block_label))
    # Split the long code string into individual lines, and discard everything before `start`:
    codelines = code.splitlines()[start:]
    # Lines containing block labels will always be of this form:
    pattern = r'^\s*-?\s*{}\s*:.*$'.format(block_label)
    # When counting items, we consider only those indented by the same amount,
    # and use indent_level to keep track of the current indentation level:
    indent_level = None
    curr_item = 0
    block_start_found = False
    for i, line in enumerate(codelines):
      # Check to see whether the current line contains the block label that we are looking for:
      matched = re.fullmatch(pattern, line)
      if matched:
        block_start_found = True
        start = start + i
        logger.debug("Found the start of the block: '{}' at line {}".format(line, start + 1))
        # If we have not been instructed to search for an item within the block, then we are done:
        if item < 0:
          return start
      elif block_start_found and item >= 0:
        # If the current line does not contain the block label, then if we have found it previously,
        # and if we are to search for the nth item within the block, then do that. If this is the
        # first item, then take note of the indentation level.
        matched = re.match(r'(\s*)-\s*\w+', line)
        item_indent_level = len(matched.group(1)) if matched else None
        if curr_item == 0:
          indent_level = item_indent_level

        # Only consider items that fall directly under this block:
        if item_indent_level == indent_level:
          logger.debug("Found item #{} of block: '{}' at line {}. Line is: '{}'"
                       .format(curr_item + 1, block_label, start + i + 1, line))
          # If we have found the nth item, return the line on which it starts:
          if curr_item == item:
            return start + i
          # Otherwise continue looping:
          curr_item += 1

    logger.debug("*** Something went wrong while trying to find the line number ***")
    return start

  if request.form.get('code') is None:
    return Response("Malformed POST request", status=400)

  try:
    code = request.form['code']
    yaml_source = yaml.load(code, Loader=yaml.SafeLoader)
    jsonschema.validate(yaml_source, schema)
  except (yaml.YAMLError, TypeError) as err:
    return (jsonify({'summary': "YAML parsing error",
                     'line_number': -1,
                     'details': format(err)}),
            400)
  except jsonschema.exceptions.ValidationError as err:
    error_summary = err.schema.get('description') or err.message
    logger.debug("Determining line number for error: {}".format(list(err.absolute_path)))
    start = 0
    if not err.absolute_path:
      return (jsonify({'summary': format(error_summary),
                       'line_number': -1,
                       'details': format(err)}),
              400)
    else:
      for component in err.absolute_path:
        if type(component) is str:
          block_label = component
          start = get_error_start(code, start, block_label)
          logger.debug("Error begins at line {}".format(start + 1))
        elif type(component) is int:
          start = get_error_start(code, start, block_label, component)
          logger.debug("Error begins at line {}".format(start + 1))

    return (jsonify({'summary': format(error_summary),
                     'line_number': start + 1,
                     'details': format(err)}),
            400)

  return Response(status=200)


def get_file_sha(repo, filename):
  """
  Get the sha of the given filename from the given github repository
  """
  response = github.get('repos/{}/contents/config/{}'.format(repo, filename))
  if not response or 'sha' not in response:
    raise Exception("Unable to get the current SHA value for {} in {}"
                    .format(filename, repo))
  return response['sha']


def get_master_sha(repo):
  """
  Get the sha for the HEAD of the master branch in the given github repository
  """
  response = github.get('repos/{}/git/ref/heads/master'.format(repo))
  if not response or 'object' not in response or 'sha' not in response['object']:
    raise Exception("Unable to get SHA for HEAD of master in {}".format(repo))
  return response['object']['sha']


def create_branch(repo, filename, master_sha):
  """
  Create a new branch, from master (identified by its sha), based on the given filename
  in the given repository.
  """
  # Generate the branch name:
  branch = "{login}_{idspace}_{utc}".format(
    login=g.user.github_login,
    idspace=filename.replace(".yml", "").upper(),
    utc=datetime.utcnow().strftime("%Y-%m-%d_%H%M%S"))

  response = github.post('repos/{}/git/refs'.format(repo),
                         data={'ref': 'refs/heads/' + branch, 'sha': master_sha})
  if not response:
    raise Exception("Unable to create new branch {} in {}".format(branch, repo))

  return branch


def commit_to_branch(repo, branch, code, filename, commit_msg, file_sha=None):
  """
  Commit the given code to the given branch in the given repo, using the given commit message.
  If the optional file_sha parameter is specified (because this commit is for an existing file)
  then include it in the request to github.
  """
  data = {'message': commit_msg,
          'content': base64.b64encode(code.encode("utf-8")).decode(),
          'branch': branch}

  if file_sha:
    data['sha'] = file_sha

  response = github.put('repos/{}/contents/config/{}'.format(repo, filename), data=data)
  if not response:
    raise Exception("Unable to commit addition of {} to branch {} in {}"
                    .format(filename, branch, repo))


def create_pr(repo, branch):
  """
  Create a pull request for the given branch in the given repository in github
  """
  response = github.post('repos/{}/pulls'.format(repo),
                         data={'title': "Request to merge branch {} to master".format(branch),
                               'head': branch,
                               'base': 'master'})
  if not response:
    raise Exception("Unable to create PR for branch {} in {}".format(branch, repo))

  return response


@app.route('/add_config', methods=['POST'])
@verify_logged_in
def add_config():
  """
  Route for initiating a pull request to add a config file to the repository
  """
  filename = request.form.get('filename')
  code = request.form.get('code')
  commit_msg = request.form.get('commit_msg')
  if any([item is None for item in [filename, commit_msg, code]]):
    return Response("Malformed POST request", status=400)

  repo = '{}/{}'.format(app.config['GITHUB_ORG'], app.config['GITHUB_REPO'])

  try:
    master_sha = get_master_sha(repo)
    new_branch = create_branch(repo, filename, master_sha)
    logger.info("Created a new branch: {} in {}".format(new_branch, repo))
    commit_to_branch(repo, new_branch, code, filename, commit_msg)
    logger.info("Committed addition of {} to branch {} in {}".format(filename, new_branch, repo))
    pr_info = create_pr(repo, new_branch)
    logger.info("Created a PR for branch {} in {}".format(new_branch, repo))
  except Exception as e:
    return Response(format(e), status=400)

  # We return github's response to the caller, which contains info on the PR (among other things,
  # a URL to use to access it):
  return jsonify({'pr_info': pr_info})


@app.route('/update_config', methods=['POST'])
@verify_logged_in
def update_config():
  """
  Route for initiating a pull request to update a config file in the github repository.
  """
  filename = request.form.get('filename')
  code = request.form.get('code')
  commit_msg = request.form.get('commit_msg')

  if any([item is None for item in [filename, commit_msg, code]]):
    return Response("Malformed POST request", status=400)

  # Get the contents of the current version of the file:
  curr_contents = github.get('repos/{}/{}/contents/config/{}'
                             .format(app.config['GITHUB_ORG'], app.config['GITHUB_REPO'], filename))
  if not curr_contents:
    raise Exception("Could not get the contents of: {}".format(path))

  decodedBytes = base64.b64decode(curr_contents['content'])
  decodedStr = str(decodedBytes, "utf-8")

  # Verify that the contents to be committed differ from the current contents, return a 422
  # if they are the same:
  if decodedStr == code:
    return Response("Update request refused: The submitted configuration is identical to the "
                    "currently saved version.", status=422)

  repo = '{}/{}'.format(app.config['GITHUB_ORG'], app.config['GITHUB_REPO'])

  try:
    file_sha = get_file_sha(repo, filename)
    master_sha = get_master_sha(repo)
    new_branch = create_branch(repo, filename, master_sha)
    logger.info("Created a new branch: {} in {}".format(new_branch, repo))
    commit_to_branch(repo, new_branch, code, filename, commit_msg, file_sha)
    logger.info("Committed update of {} to branch {} in {}".format(filename, new_branch, repo))
    pr_info = create_pr(repo, new_branch)
    logger.info("Created a PR for branch {} in {}".format(new_branch, repo))
  except Exception as e:
    return Response(format(e), status=400)

  # We return github's response to the caller, which contains info on the PR (among other things,
  # a URL to use to access it):
  return jsonify({'pr_info': pr_info})


def init_db():
  """
  Initialise the users database
  """
  Base.metadata.create_all(bind=engine)


# Call the function initialising the users db:
init_db()


if __name__ == '__main__':
  http_server = WSGIServer((app.config['FLASK_HOST'], app.config['FLASK_PORT']), app)
  http_server.serve_forever()
