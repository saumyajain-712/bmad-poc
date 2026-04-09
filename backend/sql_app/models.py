from sqlalchemy import Column, Integer, JSON, String

from .database import Base


class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True)
    api_specification = Column(String, index=True)
    status = Column(String, default="initiated")
    missing_items = Column(JSON, nullable=False, default=list)
    clarification_questions = Column(JSON, nullable=False, default=list)
    original_input = Column(String, nullable=False, default="")
    resolved_input_context = Column(String, nullable=True)
    context_version = Column(Integer, nullable=False, default=0)
    context_events = Column(JSON, nullable=False, default=list)


