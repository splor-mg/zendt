from zendt.errors import RuleInvalidError, SourceError
from zendt.rules.check_jdm import validate_jdm
from zendt.utils.paths import is_remote

""" Rule Classes"""


class RuleLocation:
    """Where one rule file lives, and the Zen key used to load it."""

    def __init__(self, origin: str, key: str) -> None:
        self.origin = origin
        self.key = key


class RuleEntry:
    """One rule file.
    `ref` is `source_id/name` when the source has an id.
    `key` is the path of the file relative to its source, without `.json`.
    """

    def __init__(
        self,
        name: str,
        source_id: str | None,
        origin: str,
        key: str,
        token: str | None = None,
    ) -> None:
        self.name = name
        self.source_id = source_id
        self.origin = origin
        self.key = key
        self.token = token

    @property
    def ref(self) -> str:
        if self.source_id:
            return f'{self.source_id}/{self.name}'
        return self.name

    def load_content(self) -> dict:
        from zendt.rules.catalog import read_local_json, request_json

        if is_remote(self.origin):
            data = request_json(self.origin, self.token)
            if not isinstance(data, dict):
                raise SourceError(
                    f'Rule JSON must be an object: {self.origin}'
                )
        else:
            data = read_local_json(self.origin)
        if not validate_jdm(data):
            raise RuleInvalidError(
                f"Rule '{self.ref}' is not a valid JDM graph."
            )
        return data


"""Source Classes"""


class ResolvedSource:
    """A source ready to catalog: path or URL, plus its token."""

    def __init__(
        self,
        source: str,
        token: str | None = None,
        version: str | None = None,
        id: str | None = None,
    ) -> None:
        self.source = source
        self.token = token
        self.version = version
        self.id = id


""" Config Classes"""


class SourceConfig:
    id: str
    source: str
    authentication: str | None
    version: str | None

    def __init__(
        self,
        id: str,
        source: str,
        authentication: str | None = None,
        version: str | None = None,
    ) -> None:
        self.id = id
        self.source = source
        self.authentication = authentication
        self.version = version


class FlowConfig:
    id: str
    description: str | None
    input: str | None
    rules: list[str]
    output: str | None

    def __init__(
        self,
        id: str,
        rules: list[str],
        description: str | None = None,
        input: str | None = None,
        output: str | None = None,
    ) -> None:
        self.id = id
        self.description = description
        self.input = input
        self.rules = rules
        self.output = output


class ZendtConfig:
    sources: list[SourceConfig]
    flows: list[FlowConfig]

    def __init__(
        self, sources: list[SourceConfig], flows: list[FlowConfig]
    ) -> None:
        self.sources = sources
        self.flows = flows
