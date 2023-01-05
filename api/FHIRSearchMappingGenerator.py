from api.ResourceQueryingMetaDataResolver import ResourceQueryingMetaDataResolver


class FHIRSearchMappingGenerator(object):
    """
    This class is responsible for generating FHIR mappings for a given FHIR profile.
    """

    def __init__(self, querying_meta_data_resolver: ResourceQueryingMetaDataResolver):
        """
        :param querying_meta_data_resolver: resolves the for the query relevant meta data for a given FHIR profile
        snapshot
        """
        self.querying_meta_data_resolver = querying_meta_data_resolver

    def generate_mapping(self):
        pass

    def resolve_fhir_search_parameter(self, element_id) -> str:
        """
        Based on the element id, this method resolves the FHIR search parameter for the given FHIR Resource attribute
        :param element_id: element id that defines the of the FHIR Resource attribute
        :return: FHIR search parameter
        """
        pass
