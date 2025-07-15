class JubError(Exception):
    http_status = 500


class AppError(JubError):
    pass


class ClientError(JubError):
    http_status = 400
