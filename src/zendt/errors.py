class ZendtError(Exception):
    exit_code = 1

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ConfigError(ZendtError):
    type = 'Configuration Error'


class SourceError(ZendtError):
    type = 'Source Error'


class AuthError(ZendtError):
    type = 'Authentication Error'


class RateLimitError(ZendtError):
    type = 'Rate Limit Exceeded'


class SourceUnavailable(ZendtError):
    type = 'Source Unavailable'


class InputError(ZendtError):
    type = 'Input Error'


class RuleNotFound(ZendtError):
    type = 'Rule Not Found'


class AmbiguousRule(ZendtError):
    type = 'Ambiguous Rule'


class EngineError(ZendtError):
    type = 'Engine Error'


class RuleInvalidError(ZendtError):
    type = 'Rule Invalid'
