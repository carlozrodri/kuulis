from typing import Literal

from pydantic import BaseModel, Field

Folder = Literal["avatars", "uploads"]


class UploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(pattern=r"^[\w.+-]+/[\w.+-]+$", max_length=100)
    size: int = Field(gt=0)
    folder: Folder = "uploads"


class UploadResponse(BaseModel):
    key: str
    upload_url: str
    method: str = "PUT"
    headers: dict[str, str]
    expires_in: int


class DownloadResponse(BaseModel):
    url: str
    expires_in: int
