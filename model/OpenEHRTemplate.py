class OpenEHRTemplate(object):
    def __init__(self, name, value_set=None, term_codes=None):
        if term_codes is None:
            term_codes = []
        if value_set is None:
            value_set = []
        self.name = name
        self.valueSets = value_set
        self.termCodes = term_codes
        self.mappingProfile = None
        self.termCodeArchitype = None
        self.valueArchitype = None
        self.annotations = {}

    def __repr__(self):
        return self.name
