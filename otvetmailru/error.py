from typing import Optional


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
    :ivar localized_message: localized error message in HTML
    """
    def __init__(self, response: dict, localized_message: Optional[str]):
        super().__init__(response["error"])
        self.response = response
        self.localized_message = localized_message


class OtvetArgumentError(OtvetError):
    """A client-side error caused by bad method arguments."""
    pass
