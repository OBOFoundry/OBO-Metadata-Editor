#!/usr/bin/env python3

import json
import jsonschema
import os
import re
import yaml
from flask import Flask, jsonify, request, make_response, Response
from github import Github


# To run in development mode, do:
# export FLASK_APP=server.py
# export FLASK_DEBUG=1 (optional)
# python3 -m flask run

app = Flask(__name__)

pwd = os.path.dirname(os.path.realpath(__file__))
schemafile = "{}/../purl.obolibrary.org/tools/config.schema.json".format(pwd)
schema = json.load(open(schemafile))


@app.route('/validate', methods=['POST'])
def validate():
  if request.form.get('code') is None:
    return Response("Malformed POST request", status=400)

  try:
    code = request.form['code']
    yaml_source = yaml.load(code)
    jsonschema.validate(yaml_source, schema)
  except yaml.YAMLError as err:
    # TODO: THIS NEEDS TO BE SENT BACK AS A JSON JUST AS BELOW:
    return Response(format(err), status=400)
  except jsonschema.exceptions.ValidationError as err:
    def get_error_start(start, block_label=None, item=None):
      print("Searching from line {} for{}block: '{}'"
            .format(start+1, ' item #{} of '.format(item+1) if item else ' ', block_label))
      pattern = '^\s*{}\s*:.*$'.format('\w+' if not block_label else block_label)
      codelines = code.splitlines()[start:]
      block_start_found = False
      curr_item = 0
      for i, line in enumerate(codelines):
        if re.fullmatch(pattern, line):
          block_start_found = True
          start = start+i
          print("Found the start of the block: '{}' at line {}".format(line, start+1))
          if not item:
            break
        elif block_start_found and item and re.match('\s*-\s*\w+:', line):
          print("Found item #{} of block: '{}' at line {}. Line is: '{}'"
                .format(curr_item+1, block_label, start+i+1, line))
          if curr_item == item:
            start = start+i
            break
          curr_item += 1

      return start

    start = 0
    if not err.absolute_path:
      start = 1
      print("Error begins at line {}".format(start+1))
    else:
      for component in err.absolute_path:
        if type(component) is str:
          block_label = component
          start = get_error_start(start, block_label)
          print("Error begins at line {}".format(start+1))
        elif type(component) is int:
          start = get_error_start(start, block_label, component)
          print("Error begins at line {}".format(start+1))

    return (jsonify({'summary': format(err.message),
                     'line_number': start+1,
                     'details': format(err)}),
            400)

  return Response(status=200)



@app.route('/save', methods=['POST'])
def save():
  filename = request.form.get('filename')
  code = request.form.get('code')
  if filename is None or code is None:
    return Response("Malformed POST request", status=400)

  # TODO: Implement git interface, pull request, etc.
  #with open('{}/github_token_do_not_commit'.format(pwd)) as f:
  #  github_token = f.readline()

  #g = Github(github_token)
  #user = g.get_user()
  #repos = user.get_repos()
  #myrepo = [repo for repo in list(repos) if repo.name == 'purl-editor'].pop()
  #boofy = myrepo.name
  #print(boofy)
  
  return Response(status=200)
