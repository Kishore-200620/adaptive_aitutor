from app.database.connection import Base, engine
from app import models


def init_database():
    Base.metadata.create_all(bind=engine)
    print("DATABASE TABLES CREATED SUCCESSFULLY")


if __name__ == "__main__":
    init_database()
    