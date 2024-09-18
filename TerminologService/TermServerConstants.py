import os

import requests

TERMINOLOGY_SERVER_ADDRESS = os.environ.get('ONTOLOGY_SERVER_ADDRESS')
SERVER_CERTIFICATE = os.environ.get('SERVER_CERTIFICATE')
PRIVATE_KEY = os.environ.get('PRIVATE_KEY')
REQUESTS_SESSION = requests.Session()
