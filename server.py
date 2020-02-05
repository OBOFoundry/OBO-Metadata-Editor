#!/usr/bin/env python3

import base64
import functools
import json
import jsonschema
import os
import re
import yaml

from authlib.integrations.flask_client import OAuth
from flask import Flask, jsonify, redirect, render_template, request, Response, \
  send_from_directory, session, url_for


# To run in development mode, do:
# export GITHUB_CLIENT_ID=<client id for this application>
# export GITHUB_CLIENT_SECRET<client secret for this application>
# export FLASK_APP=server.py
# export FLASK_DEBUG=1 (optional)
# python3 -m flask run

app = Flask(__name__)
app.secret_key = os.urandom(16)
app.config.from_object('config')

# Register the github OAUth App 'purl_editor' which will take care of the integration with github:
oauth = OAuth(app)
oauth.register(
  name=app.config['OAUTH_APP_NAME'],
  client_id=app.config['GITHUB_CLIENT_ID'],
  client_secret=app.config['GITHUB_CLIENT_SECRET'],
  access_token_url=app.config['ACCESS_TOKEN_URL'],
  access_token_params=app.config['ACCESS_TOKEN_PARAMS'],
  authorize_url=app.config['AUTHORIZE_URL'],
  authorize_params=app.config['AUTHORIZE_PARAMS'],
  api_base_url=app.config['API_BASE_URL'],
  client_kwargs={'scope': 'user:email'},
)

oauth2_tokens = {}

pwd = os.path.dirname(os.path.realpath(__file__))
schemafile = "{}/../purl.obolibrary.org/tools/config.schema.json".format(pwd)
schema = json.load(open(schemafile))

# Use this to troubleshoot parsing errors:
debug_enabled = False
def debug(statement):
  debug_enabled and print(statement)


def github_authorize(fn):
    """
    Wrapper function to verify the session authorization, and authorize if not already authorized.
    """
    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
      if not session.get('user'):
        redirect_uri = url_for('github_auth_callback_route', _external=True)
        return oauth.purl_editor.authorize_redirect(redirect_uri)
      return fn(*args, **kwargs)

    return wrapped


@app.route('/logged_in', methods=['GET'])
@github_authorize
def logged_in():
  """
  Indicates to the user that authentication has just taken place.
  """
  return \
    """
    <!doctype html>

    <title>OBO PURL YAML Code Editor</title>
    <meta charset="utf-8"/>
    <meta http-equiv="refresh" content="3;url=/" />

    <div>
    <h4>
    Your session was no longer valid and has been re-authenticated.
    If you are not redirected in 3 seconds click <a href="/">here</a>.
    </h4>
    </div>
    """


@app.route('/github_auth_callback_route')
def github_auth_callback_route():
  """
  Callback route for API requests to github
  """
  token = oauth.purl_editor.authorize_access_token()
  if not token:
    raise Exception("Token could not be authorized")

  profile = oauth.purl_editor.get('user', token=token)
  if not profile:
    raise Exception("Profile could not be extracted")

  # MAYBE WE SHOULD USE HTML5 WEB STORAGE INSTEAD OF A COOKIE.
  # (see https://security.stackexchange.com/questions/80727/best-place-to-store-authentication-tokens-client-side)
  profile = profile.json()
  session['user'] = profile['login']
  oauth2_tokens[profile['login']] = token
  return redirect('/logged_in')


@app.route('/', methods=['GET'])
@github_authorize
def root():
  """
  Renders the root page of the application
  """
  configs = oauth.purl_editor.get(
    'repos/{}/purl.obolibrary.org/contents/config'.format(session['user']),
    token=oauth2_tokens[session['user']])
  if not configs:
    raise Exception("Could not get contents of the config directory")

  return render_template('index.jinja2', configs=configs.json())

@app.route('/edit_new', methods=['GET'])
@github_authorize
def edit_new():
  return render_template('purl_editor.jinja2')


@app.route('/edit/<path:path>', methods=['GET'])
@github_authorize
def edit_github(path):
  """
  Gets the contents of the given path from the purl.obolibrary.org repository and renders it in the
  editor using a html template file.
  """
  config_file = oauth.purl_editor.get(
    'repos/{}/purl.obolibrary.org/contents/{}'.format(session['user'], path),
    token=oauth2_tokens[session['user']])
  if not config_file:
    raise Exception("Could not get the contents of: {}".format(path))
  config_file = config_file.json()

  decodedBytes = base64.b64decode(config_file['content'])
  decodedStr = str(decodedBytes, "utf-8")
  return render_template('purl_editor.jinja2', yaml=decodedStr, idspace=config_file['name'])


@app.route('/<path:path>')
@github_authorize
def send_editor_page(path):
  """
  Route for serving up static files, including third party libraries.
  """
  return send_from_directory(pwd, path, as_attachment=False)


@app.route('/validate', methods=['POST'])
@github_authorize
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
    debug("Searching from line {} for{}block: '{}'"
          .format(start + 1, ' item #{} of '.format(item + 1) if item >= 0 else ' ', block_label))
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
        debug("Found the start of the block: '{}' at line {}".format(line, start + 1))
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
          debug("Found item #{} of block: '{}' at line {}. Line is: '{}'"
                .format(curr_item + 1, block_label, start + i + 1, line))
          # If we have found the nth item, return the line on which it starts:
          if curr_item == item:
            return start + i
          # Otherwise continue looping:
          curr_item += 1

    debug("*** Something went wrong while trying to find the line number ***")
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
    debug("Determining line number for error: {}".format(list(err.absolute_path)))
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
          debug("Error begins at line {}".format(start + 1))
        elif type(component) is int:
          start = get_error_start(code, start, block_label, component)
          debug("Error begins at line {}".format(start + 1))

    return (jsonify({'summary': format(error_summary),
                     'line_number': start + 1,
                     'details': format(err)}),
            400)

  return Response(status=200)


@app.route('/create_pr', methods=['POST'])
@github_authorize
def pr():
  """
  Route for initiating a pull request against the github repository.
  """
  filename = request.form.get('filename')
  code = request.form.get('code')
  if filename is None or code is None:
    return Response("Malformed POST request", status=400)

  return Response(status=200)
