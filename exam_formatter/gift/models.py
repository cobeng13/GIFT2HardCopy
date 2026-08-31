from dataclasses import dataclass


@dataclass(frozen=True)
class Choice:
    text: str
    correct: bool


@dataclass(frozen=True)
class Question:
    stem: str
    choices: tuple[Choice, ...]
    title: str | None = None
