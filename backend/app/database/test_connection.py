from sqlalchemy import text

from app.database.connection import engine


try:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT version();"))

        print("DATABASE CONNECTION SUCCESSFUL")
        print(result.scalar())

except Exception as e:
    print("DATABASE CONNECTION FAILED")
    print(e)
    