from enum import Enum


class BundleType(Enum):
    DOCUMENT = "document"
    MESSAGE = "message"
    TRANSACTION = "transaction"
    TRANSACTION_RESPONSE = "transaction-response"
    BATCH = "batch"
    BATCH_RESPONSE = "batch-response"
    HISTORY = "history"
    SEARCHSET = "searchset"
    COLLECTION = "collection"


def create_bundle(bundle_type: BundleType):
    return {
        "resourceType": "Bundle",
        "type": bundle_type.value,
        "entry": []
    }
