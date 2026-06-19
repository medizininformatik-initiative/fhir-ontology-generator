import re

MII_CDS_PACKAGE_PATTERN = {
    "name": re.compile(r"de\.medizininformatikinitiative\.kerndatensatz")
}
GEMATIK_PACKAGE_PATTERN = {
    "name": re.compile(r"de\.gematik\.isik")
}

FLATTENING_PACKAGE_PATTERN = {"name": re.compile(r"de\.gematik\.isik|de\.medizininformatikinitiative\.kerndatensatz")}
