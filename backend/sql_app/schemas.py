from pydantic import BaseModel


class RunBase(BaseModel):
    api_specification: str


class RunCreate(RunBase):
    pass


class Run(RunBase):
    id: int
    status: str

    class Config:
        orm_mode = True
