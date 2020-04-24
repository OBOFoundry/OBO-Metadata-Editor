# OBO Metadata Editor

A web based editor for modifying existing and creating new OBO Metadata configurations.

## Before running the server:

1. Install the necessary python dependencies using `pip` by navigating to the directory in which `server.py` is located and running the following command:
```
pip install -r requirements.txt
```

2. Make sure that the following environment variables have been set:

- GITHUB_CLIENT_ID
- GITHUB_CLIENT_SECRET
- FLASK_SECRET_KEY

To obtain the values for the first two settings, send an email to james@overton.ca. For the value of `FLASK_SECRET_KEY`, a randomly generated string may be used.

3. Edit the file `config.py` and make sure that the configuration settings are correct. Note in particular the settings for `FLASK_PORT`, `LOG_LEVEL`, `GITHUB_ORG`, `SCHEMAFILE`, and `ONTOLOGY_METADATA_URL`.
- `LOG_LEVEL` should be set to one of: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (_without_ quotes).
- `FLASK_PORT` should be set to the port on which the server will be listening.
- `GITHUB_ORG` should be set to the organization or username that owns the repository. Normally it should be set to `OBOFoundry`.
- `SCHEMAFILE` is the location of the jsonschema file that will be used to validate YAML code.
- `ONTOLOGY_METADATA_URL` is the URL from which descriptive information about various ontologies can be found.

## Running the server

- Navigate to the directory in which `server.py` is located, and then run the following commands:
```
export FLASK_APP=server.py
export FLASK_DEBUG=1 (optional)
python3 -m flask run
```
