from fastapi import FastAPI, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from contextlib import asynccontextmanager 

from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware # New import for CORS

from auth import get_password_hash, verify_password, create_access_token, get_current_user
from schemas import UserCreate, UserPublic


from database import get_session, create_db_and_tables
from models import (
    User, Post, Comment,
    UserCreate, UserPublic,
    PostCreate, PostPublic, PostPublicWithOwner, PostPublicWithComments,
    CommentCreate, CommentPublic, CommentPublicWithUser
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("App is starting up...")
    # This is the code that runs on startup
    create_db_and_tables()
    print("Database tables created.")
    yield # This yield separates startup code from shutdown code
    print("App is shutting down...")
    

# Create the FastAPI app object
# And connect the new lifespan handler
app = FastAPI(lifespan=lifespan)


# --- User Routes ---
@app.post("/users/", response_model=UserPublic)
def create_user(user: UserCreate, session: Session = Depends(get_session)):
    """Creates a new user."""
    # Check if user already exists
    existing = session.exec(select(User).where(User.email == user.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    db_user = User.model_validate(user)
    
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user

@app.get("/users/", response_model=List[UserPublic])
def read_users(session: Session = Depends(get_session)):
    """Returns a list of all users."""
    users = session.exec(select(User)).all()
    return users


@app.post("/posts/", response_model=PostPublic)
def create_post(post: PostCreate, session: Session = Depends(get_session)):
    """Creates a new post."""
    # Check if the owner (user) exists
    user = session.get(User, post.owner_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    db_post = Post.model_validate(post)
    
    session.add(db_post)
    session.commit()
    session.refresh(db_post)
    return db_post

@app.get("/posts/", response_model=List[PostPublicWithOwner])
def read_posts(session: Session = Depends(get_session)):
    """Returns a list of all posts, including their owners."""
    posts = session.exec(select(Post)).all()
    return posts

@app.get("/posts/{post_id}", response_model=PostPublicWithComments)
def read_post(post_id: int, session: Session = Depends(get_session)):
    """Returns a single post by its ID, including its owner and comments."""
    post = session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@app.put("/posts/{post_id}", response_model=PostPublic)
def update_post(post_id: int, post_update: PostCreate, session: Session = Depends(get_session)):
    """Updates an existing post."""
    db_post = session.get(Post, post_id)
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Check if the new owner exists
    user = session.get(User, post_update.owner_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get the data from the request
    update_data = post_update.model_dump(exclude_unset=True)
    
    # Update the model
    db_post.sqlmodel_update(update_data)
    
    session.add(db_post)
    session.commit()
    session.refresh(db_post)
    return db_post

@app.delete("/posts/{post_id}")
def delete_post(post_id: int, session: Session = Depends(get_session)):
    """Deletes a post."""
    post = session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    session.delete(post)
    session.commit()
    return {"message": "Post deleted successfully"}


@app.post("/posts/{post_id}/comments/", response_model=CommentPublic)
def create_comment(post_id: int, comment: CommentCreate, session: Session = Depends(get_session)):
    """Creates a new comment on a specific post."""
    post = session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    user = session.get(User, comment.owner_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    db_comment = Comment.model_validate(comment, update={"post_id": post_id})
    
    session.add(db_comment)
    session.commit()
    session.refresh(db_comment)
    return db_comment

@app.get("/posts/{post_id}/comments/", response_model=List[CommentPublicWithUser])
def read_comments_for_post(post_id: int, session: Session = Depends(get_session)):
    """Returns all comments for a specific post."""
    post = session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    return post.comments

@app.get("/comments/{comment_id}", response_model=CommentPublicWithUser)
def read_comment(comment_id: int, session: Session = Depends(get_session)):
    """Returns a single comment by its ID."""
    comment = session.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    return comment

@app.put("/comments/{comment_id}", response_model=CommentPublic)
def update_comment(comment_id: int, comment_update: CommentCreate, session: Session = Depends(get_session)):
    """Updates an existing comment."""
    db_comment = session.get(Comment, comment_id)
    if not db_comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    user = session.get(User, comment_update.owner_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = comment_update.model_dump(exclude_unset=True)
    db_comment.sqlmodel_update(update_data)
    
    session.add(db_comment)
    session.commit()
    session.refresh(db_comment)
    return db_comment

@app.delete("/comments/{comment_id}")
def delete_comment(comment_id: int, session: Session = Depends(get_session)):
    """Deletes a comment."""
    comment = session.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
        
    session.delete(comment)
    session.commit()
    return {"message": "Comment deleted successfully"}

@app.post("/register", response_model=UserPublic, tags=["auth"])
def register_user(user_in: UserCreate, session: Session = Depends(get_session)):
    """Registers a new user and hashes the password."""
    # 1. Check if user already exists
    existing = session.exec(select(User).where(User.email == user_in.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # 2. Hash the password securely
    hashed_password = get_password_hash(user_in.password)
    
    # 3. Create the database model
    db_user = User(
        email=user_in.email, 
        password_hash=hashed_password
    )
    
    # 4. Save to DB
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    
    # Return the public-facing model
    return db_user