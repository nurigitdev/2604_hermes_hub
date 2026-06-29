from pydantic import BaseModel, EmailStr


class CurrentAdminResponse(BaseModel):
    id: int
    email: EmailStr
    name: str | None
    role: str
