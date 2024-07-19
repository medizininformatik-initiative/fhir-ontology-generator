import json
import os

TERMINOLOGY_SERVER_ADDRESS = os.environ.get('ONTOLOGY_SERVER_ADDRESS')
SERVER_CERTIFICATE = os.environ.get('SERVER_CERTIFICATE')
PRIVATE_KEY = os.environ.get('PRIVATE_KEY')

# Get the current working directory
current_working_dir = os.getcwd()
print(current_working_dir)
mapping_path = os.environ.get('ONTO_MAPPING_PATH', os.path.join(current_working_dir, '..', '..', 'mapping.json'))
with open(mapping_path, 'r') as file:
    MAPPING_ONTO_VERSION = json.load(file)