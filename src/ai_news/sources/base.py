from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FeedSource:
    name: str
    url: str
    priority: int
    is_official: bool = True
