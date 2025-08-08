"""Skill SQLModel for operator capabilities."""

from datetime import datetime

from sqlmodel import Field, SQLModel


class SkillBase(SQLModel):
    """Base skill fields."""

    skill_code: str = Field(max_length=20, unique=True, index=True)
    skill_name: str = Field(max_length=100)
    skill_category: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None)


class Skill(SkillBase, table=True):
    """
    Skill table model.

    Represents skills that operators can have and machines can require.
    """

    __tablename__ = "skills"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow}
    )


class SkillCreate(SkillBase):
    """Skill creation model."""

    pass


class SkillUpdate(SQLModel):
    """Skill update model."""

    skill_name: str | None = Field(default=None, max_length=100)
    skill_category: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None)


class SkillRead(SkillBase):
    """Skill read model."""

    id: int
    created_at: datetime
    updated_at: datetime
