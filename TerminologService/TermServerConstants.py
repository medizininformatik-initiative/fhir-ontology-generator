import json
import os

TERMINOLOGY_SERVER_ADDRESS = os.environ.get('ONTOLOGY_SERVER_ADDRESS')
SERVER_CERTIFICATE = os.environ.get('SERVER_CERTIFICATE')
PRIVATE_KEY = os.environ.get('PRIVATE_KEY')
mapping_path = os.environ.get('ONTO_MAPPING_PATH', "../mapping.json")
with open(mapping_path, 'r') as file:
    MAPPING_ONTO_VERSION = json.load(file)

