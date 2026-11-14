from typing import Any

type SelectOptionDict = dict[str, Any]

class SelectSelectorConfig:
    def __init__(
        self, *, options: list[SelectOptionDict], multiple: bool = False
    ) -> None: ...

class SelectSelector:
    def __init__(self, config: SelectSelectorConfig) -> None: ...
