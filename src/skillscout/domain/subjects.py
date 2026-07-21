"""Run-authority contract for one remote GitHub repository subject."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AfterValidator, Field, model_validator

from skillscout.domain.models import StrictFrozenModel

SubjectId = Annotated[
    str,
    Field(
        min_length=8,
        max_length=128,
        pattern=r"^repo:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$",
    ),
]
RepositoryUrl = Annotated[
    str,
    Field(
        min_length=20,
        max_length=300,
        pattern=r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?$",
    ),
]

_URL_PREFIX = "https://github.com/"


def _reject_ref_sequences(value: str) -> str:
    """Reject the closed set of ref sequences the pattern alone cannot express."""

    if (
        ".." in value
        or value.startswith("/")
        or value.endswith("/")
        or "\\" in value
        or "@{" in value
    ):
        raise ValueError("subject ref contains a rejected sequence")
    return value


SubjectRef = Annotated[
    str,
    Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$"),
    AfterValidator(_reject_ref_sequences),
]


class RepositorySubject(StrictFrozenModel):
    """The complete phase-two run input selecting one remote repository."""

    schema_version: Literal["1"]
    subject_id: SubjectId
    repository: RepositoryUrl
    ref: SubjectRef | None = None

    @model_validator(mode="after")
    def validate_subject_matches_url(self) -> RepositorySubject:
        path = self.repository.removeprefix(_URL_PREFIX).removesuffix(".git")
        if self.subject_id != f"repo:{path}":
            raise ValueError("subject_id and repository URL disagree")
        return self
