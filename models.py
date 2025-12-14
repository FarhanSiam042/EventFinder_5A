from sqlmodel import Field, Relationship, SQLModel
from typing import Optional, List

class User(SQLModel, table=True):
   id: Optional[int] = Field(default=None, primary_key=True)
   email: str = Field(index=True, unique=True)
  
   password_hash: str 

    # 1-to-Many relationship: One User can have many Posts
   posts: List["Post"] = Relationship(back_populates="owner")
    # 1-to-Many relationship: One User can have many Comments
   comments: List["Comment"] = Relationship(back_populates="owner")

class Post(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    content: str
    
    # Many-to-1 relationship: Many Posts can belong to one User
    owner_id: int = Field(foreign_key="user.id")
    owner: User = Relationship(back_populates="posts")
    
    # 1-to-Many relationship: One Post can have many Comments
    comments: List["Comment"] = Relationship(back_populates="post")

class Comment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    body: str
    
    # Many-to-1 relationship: Many Comments can belong to one User
    owner_id: int = Field(foreign_key="user.id")
    owner: User = Relationship(back_populates="comments")
    
    # Many-to-1 relationship: Many Comments can belong to one Post
    post_id: int = Field(foreign_key="post.id")
    post: Post = Relationship(back_populates="comments")


# --- User Schemas ---
class UserBase(SQLModel):
    email: str

class UserCreate(UserBase):
    # In Lab 2, we will add a password field here
    pass

class UserPublic(UserBase):
    id: int

# --- Comment Schemas ---
class CommentBase(SQLModel):
    body: str

class CommentCreate(CommentBase):
    # For Lab 1, the user must manually specify who they are
    # In Lab 2, we will get this from the auth token
    owner_id: int

class CommentPublic(CommentBase):
    id: int
    owner_id: int # Send the owner_id

# A special schema for returning a Comment with its User
class CommentPublicWithUser(CommentPublic):
    owner: UserPublic # Return the nested User object

# --- Post Schemas ---
class PostBase(SQLModel):
    title: str
    content: str

class PostCreate(PostBase):
    # For Lab 1, the user must manually specify who they are
    # In Lab 2, we will get this from the auth token
    owner_id: int

class PostPublic(PostBase):
    id: int
    owner_id: int # Send the owner_id

# A special schema for returning a Post with its User
class PostPublicWithOwner(PostPublic):
    owner: UserPublic # Return the nested User object

# A special schema for GET /posts/{id}
# It includes the post, its owner, and all its comments
class PostPublicWithComments(PostPublicWithOwner):
    comments: List[CommentPublic] = []