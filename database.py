from sqlmodel import SQLModel, create_engine, Session
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Get the database URL from the environment
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in the .env file")

# The engine is the one object that manages connections to the DB
# echo=True will print all the raw SQL queries it runs (good for debugging)
engine = create_engine(DATABASE_URL, echo=True)

def get_session():
    with Session(engine) as session:
        yield session

def create_db_and_tables():
    # SQLModel.metadata.create_all() checks if tables exist
    # before creating them, so it's safe to run every time.
    SQLModel.metadata.create_all(engine)