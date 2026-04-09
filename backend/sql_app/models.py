from sqlalchemy import Column, Integer, JSON, String

from .database import Base


class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True)
    api_specification = Column(String, index=True)
    status = Column(String, default="initiated")
    missing_items = Column(JSON, nullable=False, default=list)
    clarification_questions = Column(JSON, nullable=False, default=list)


