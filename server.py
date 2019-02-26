#!/usr/bin/env python3

import json
import jsonschema
import os
import yaml
from flask import Flask, request, Response


app = Flask(__name__)

pwd = os.path.dirname(os.path.realpath(__file__))
schemafile = "{}/../purl.obolibrary.org/tools/config.schema.json".format(pwd)
schema = json.load(open(schemafile))


@app.route('/validate', methods=['POST'])
def validate():
  if request.form.get('code') is None:
    return Response("Malformed POST request", status=400)

  try:
    yaml_source = yaml.load(request.form['code'])
    jsonschema.validate(yaml_source, schema)
  except (yaml.YAMLError, jsonschema.exceptions.ValidationError) as err:
    return Response(format(err), status=400)

  return Response(status=200)
