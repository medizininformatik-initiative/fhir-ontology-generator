import logging


class ClassNameFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, "className"):
            record.className = ""
        return record
