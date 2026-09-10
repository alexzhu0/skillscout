"""Explicit, versioned local README input; ordinary repository inputs stay frozen."""

import re
from typing import Literal

from pydantic import model_validator

from skillscout.domain.reading import validate_repo_path
from skillscout.domain.subjects import RepositorySubject


LOCAL_README_SCOPE_KEY = "local_readme_scope"
LOCAL_README_POLICY_VERSION = "reader-selected-readme-v1"


class LocalReadmeSubject(RepositorySubject):
    """One operator-selected inert README at an immutable public repository SHA."""

    scope_version: Literal["local-readme-v1"] = "local-readme-v1"
    readme_path: str

    @model_validator(mode="after")
    def validate_local_selection(self) -> "LocalReadmeSubject":
        if (
            self.ref is None
            or re.fullmatch(r"[0-9a-f]{40}", self.ref) is None
            or not validate_repo_path(self.readme_path)
            or "." in self.readme_path.split("/")
            or self.readme_path.rsplit("/", 1)[-1].lower() != "readme.md"
        ):
            raise ValueError("local README selection rejected")
        return self
