import json
import os

from util.auth.authentication import OAuthClientCredentials
from util.backend.FeasibilityBackendClient import FeasibilityBackendClient
from test_backend import get_patient_files
from util.test.fhir import load_list_of_resources_onto_fhir_server

if __name__ == '__main__':
    auth = OAuthClientCredentials(
        client_credentials=("dataportal-webapp", "piczMMlNFoQuKTjRT4o4FJibPUFuI2bk"),
        token_access_url="http://localhost:8083/auth/realms/dataportal/protocol/openid-connect/token",
        user_credentials=("test", "supersecretpassword")
    )
    client = FeasibilityBackendClient("http://localhost:8091/api/v4", auth)

    #query_resource_path="testdata/kds-testdata-2024.0.1/resources"
    re = get_patient_files("Patient-mii-exa-test-data-patient-1.json","testdata/kds-testdata-2024.0.1/resources")
    print(re)
    loaded = load_list_of_resources_onto_fhir_server("http://localhost:8082/fhir",re,"testdata/kds-testdata-2024.0.1/resources")
    print(loaded)


    with open(os.path.join("test_querys","BioprobeQueryPatient3.json"),"r",encoding="utf-8") as f:
        query = json.dumps(json.load(f))

    print(client.validate_query(query))

    location = client.query(query)
    query_id = location.split("/")[-1]


    query_result = client.get_query_summary_result(query_id)
    print(query_result)
    assert int(query_result.get("totalNumberOfPatients")) >= 1





