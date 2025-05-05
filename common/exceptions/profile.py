from common.exceptions import NotFoundError


class MissingProfileError(NotFoundError):
    pass

class MissingElementError(NotFoundError):
    pass