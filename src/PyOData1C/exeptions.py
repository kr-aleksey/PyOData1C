class ClientConnectionError(ConnectionError):
    pass

class ODataError(Exception):
    pass

class ResponseError(ODataError):
    def __init__(self, status, reason, details):
        super().__init__(
            f'Status: {status}. Reason: {reason}. Details: {details}')

