from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

Credits = Annotated[int, Field(strict=True, gt=0, le=10**12)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OwnerCreate(Input):
    name: str = Field(min_length=1, max_length=120)


class AgentCreate(Input):
    name: str = Field(min_length=1, max_length=120)
    framework: str = Field(min_length=1, max_length=80)
    endpoint: HttpUrl
    capacity: int = Field(default=1, strict=True, ge=1, le=100)

    @field_validator("endpoint")
    @classmethod
    def require_https(cls, value):
        if value.scheme != "https":
            raise ValueError("Agent endpoints must use HTTPS")
        return value


class Availability(Input):
    available: bool = Field(strict=True)


class SkillCreate(Input):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)
    version: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1, max_length=8000)
    input_schema: dict = Field(default_factory=dict)
    output_schema: dict = Field(default_factory=dict)


class Funding(Input):
    amount: Credits


class ProjectCreate(Input):
    title: str = Field(min_length=1, max_length=200)
    budget: Credits


class TaskCreate(Input):
    agent_id: str = Field(min_length=36, max_length=36)
    skill_id: str = Field(min_length=36, max_length=36)
    instructions: str = Field(min_length=1, max_length=16000)
    acceptance_criteria: str = Field(min_length=1, max_length=8000)
    price: Credits


class Submission(Input):
    artifact: dict

    @field_validator("artifact")
    @classmethod
    def nonempty(cls, value):
        if not value:
            raise ValueError("A deliverable is required")
        return value


class Lease(Input):
    lease_seconds: int = Field(default=300, strict=True, ge=30, le=900)
