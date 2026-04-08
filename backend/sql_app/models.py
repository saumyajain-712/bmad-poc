from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship

from .database import Base


class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True)
    api_specification = Column(String, index=True)
    status = Column(String, default="initiated")
    # Add more fields as needed for the run details


