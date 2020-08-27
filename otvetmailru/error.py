class OtvetError(Exception):
    """Base class for all library errors."""
    pass


class OtvetAuthError(OtvetError):
    """
    Authentication error.
    :ivar login: a username of the account that failed authentication
    """

    def __init__(self, login: str):

        super().__init__(f'Authentication failed for "{login}"')
        self.login = login


class OtvetAPIError(OtvetError):
    """
    An error returned from the API.
    :ivar response: API response as dict
    """
    def __init__(self, response: dict):
        super().__init__(response["error"])
        self.response = response


class OtvetArgumentError(OtvetError):
    """A client-side error caused by bad method arguments."""
    pass
