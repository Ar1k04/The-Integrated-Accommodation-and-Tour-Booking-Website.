from pydantic import BaseModel


class PaginationMeta(BaseModel):
    total: int
    page: int
    per_page: int
    total_pages: int


class ListResponse(BaseModel):
    items: list
    meta: PaginationMeta


class MessageResponse(BaseModel):
    success: bool = True
    message: str
