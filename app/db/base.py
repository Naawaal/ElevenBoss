from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """
    SQLAlchemy 2.x style DeclarativeBase for future model inheritance.
    All models in the application should inherit from this Base to be 
    correctly mapped and picked up by Alembic's autogeneration.
    """
    pass
