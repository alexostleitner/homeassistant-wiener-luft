from collections.abc import Callable, Iterable
from typing import Any

type AddEntitiesCallback = Callable[[Iterable[Any]], None]
