
from sqlmodel import SQLModel
from typing import Optional, List


class UserBase(SQLModel):
    email: str


class UserCreate(UserBase):
    password: str 


class UserPublic(UserBase):
    id: int
    

class EventCreate(SQLModel):
    name: str
    description: str
    location: str
   
    
class EventPublic(SQLModel):
    id: int
    name: str
    description: str
    location: str
    organizer_id: int 