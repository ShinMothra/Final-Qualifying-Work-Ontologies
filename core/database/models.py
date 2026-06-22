from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    full_name = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    ontologies = relationship("Ontology", back_populates="author")


class Ontology(Base):
    __tablename__ = "ontologies"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    author_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_public = Column(Boolean, default=True)

    author = relationship("User", back_populates="ontologies")
    versions = relationship("OntologyVersion", back_populates="ontology", cascade="all, delete-orphan")
    latest_version = relationship("OntologyVersion", uselist=False, viewonly=True,
                                  primaryjoin="and_(Ontology.id==OntologyVersion.ontology_id, "
                                              "OntologyVersion.is_latest==True)")


class OntologyVersion(Base):
    __tablename__ = "ontology_versions"
    id = Column(Integer, primary_key=True)
    ontology_id = Column(Integer, ForeignKey("ontologies.id"), nullable=False)
    version = Column(String(20), nullable=False)
    owl_content = Column(Text, nullable=False)
    comment = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_latest = Column(Boolean, default=True)

    ontology = relationship("Ontology", back_populates="versions")