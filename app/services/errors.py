class ServiceError(Exception):
    status = 400

    def __init__(self, detail: str, code: str = "error"):
        super().__init__(detail)
        self.detail = detail
        self.code = code


class NotFound(ServiceError):
    status = 404


class Forbidden(ServiceError):
    status = 403


class Conflict(ServiceError):
    status = 409


class TooMany(ServiceError):
    status = 429
