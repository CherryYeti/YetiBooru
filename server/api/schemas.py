from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel


@dataclass
class Category:
    label: str
    color: str


@dataclass
class Tag:
    category: Category
    count: int
    label: str
    id: int


@dataclass
class Post:
    id: int
    score: int
    tags: list[Tag]
    type: Literal["video", "image"]
    media_ext: str
    uploaded_at: str
    uploader_name: str | None
    media_width: int | None
    media_height: int | None
    source_url: str | None


class CreateTagRequest(BaseModel):
    label: str
    category_id: int | None = None


class UpdateImplicationsRequest(BaseModel):
    implied_tag_labels: list[str]


class UpdateTagRequest(BaseModel):
    category_label: str


class CreateCategoryRequest(BaseModel):
    label: str
    color: str


class UpdateCategoryRequest(BaseModel):
    label: str
    color: str


class UpdatePostTagsRequest(BaseModel):
    tag_labels: list[str]


class UserInfo(BaseModel):
    id: str
    name: str
    email: str
    role: Literal["owner", "admin", "moderator", "user"]
    banned: bool
    ban_reason: str | None = None
    ban_expires: str | None = None


class UpdateUserRoleRequest(BaseModel):
    role: Literal["owner", "admin", "moderator", "user"]


class UpdateUserBanRequest(BaseModel):
    banned: bool
    reason: str | None = None
