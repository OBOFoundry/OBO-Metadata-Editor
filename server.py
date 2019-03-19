#!/usr/bin/env python3

import json
import jsonschema
import os
import re
import yaml
from flask import Flask, jsonify, request, Response


# To run in development mode, do:
# export FLASK_APP=server.py
# export FLASK_DEBUG=1 (optional)
# python3 -m flask run

app = Flask(__name__)

pwd = os.path.dirname(os.path.realpath(__file__))
schemafile = "{}/../purl.obolibrary.org/tools/config.schema.json".format(pwd)
schema = json.load(open(schemafile))


# Use this to troubleshoot parsing errors:
debug_enabled = True
def debug(statement):
  debug_enabled and print(statement)


@app.route('/validate', methods=['POST'])
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
    pattern = '^(\s*)-?\s*{}\s*:.*$'.format(block_label)
    # When counting items, we consider only those indented by the same amount as the block label,
    # and use indent_level to keep track of the current indentation level:
    indent_level = None
    curr_item = 0
    block_start_found = False
    for i, line in enumerate(codelines):
      # Check to see whether the current line contains the block label that we are looking for:
      matched = re.fullmatch(pattern, line)
      if matched:
        # If it does, then take note of its indentation level and record that we have found it:
        if indent_level is None:
          indent_level = len(matched.group(1))
        block_start_found = True
        start = start + i
        debug("Found the start of the block: '{}' at line {} (indentation level: {})"
              .format(line, start + 1, indent_level))
        # If we have not been instructed to search for an item within the block, then we are done:
        if item < 0:
          return start
      elif block_start_found and item >= 0:
        # If the current line does not contain the block label, then if we have found it previously,
        # and if we are to search for the nth item within the block, then do that:
        matched = re.match('(\s*)-\s*\w+', line)
        # Only consider items that fall directly under this block:
        item_indent_level = len(matched.group(1)) if matched else None
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
    yaml_source = yaml.load(code)
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


@app.route('/save', methods=['POST'])
def save():
  filename = request.form.get('filename')
  code = request.form.get('code')
  if filename is None or code is None:
    return Response("Malformed POST request", status=400)

  return Response(status=200)
