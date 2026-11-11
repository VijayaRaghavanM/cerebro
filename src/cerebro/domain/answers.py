"""What an answer is built from and cites."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    """A page an answer can cite."""

    title: str
    url: str
