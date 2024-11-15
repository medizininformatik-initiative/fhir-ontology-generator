from enum import Enum


BundleType = Enum('BundleType', ['document', 'message', 'transaction', 'transaction-response', 'batch',
                                 'batch-response', 'history', 'searchset', 'collection'])


def create_bundle(bundle_type: BundleType):
    return {
        "resourceType": "Bundle",
        "type": bundle_type,
        "entry": []
    }
