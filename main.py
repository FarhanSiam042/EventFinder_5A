# main.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from typing import List
from contextlib import asynccontextmanager

# Local Module Imports
from database import get_session, create_db_and_tables
from models import User, Post, Comment
# NOTE: The models imported here are the SQLModel (table=True) classes.
from schemas import (
    UserCreate, UserPublic,
    PostCreate, PostPublic, PostPublicWithOwner, PostPublicWithComments,
    CommentCreate, CommentPublic, CommentPublicWithUser
)
# NOTE: The schemas imported here are the Pydantic classes for request/response bodies.
from auth import get_password_hash, verify_password, create_access_token, get_current_user

# --- CORS Configuration ---
# Fix CORS (Task 3.4): Allows a frontend running on a different domain/port to access the API.
origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:3000",
    "*"  # WARNING: Replace with specific frontend domains in production
]

# --- Application Lifespan Handler ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup (DB creation) and shutdown events."""
    print("App is starting up...")
    create_db_and_tables()
    print("Database tables created.")
    yield
    print("App is shutting down...")


# Create the FastAPI app object
app = FastAPI(lifespan=lifespan)

# Add the CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],    # Crucial for allowing Authorization header
)


# =========================================================================
# --- Authentication & User Routes (Task 2 & 3) ---
# =========================================================================

@app.post("/register", response_model=UserPublic, tags=["auth"])
def register_user(user_in: UserCreate, session: Session = Depends(get_session)):
    """Registers a new user and hashes the password (Task 2)."""
    # 1. Check if user already exists
    existing = session.exec(select(User).where(
        User.email == user_in.email)).first()
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

    return db_user


@app.post("/login", tags=["auth"])
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session)
):
    """Authenticates a user and returns an access token (Task 3.1)."""
    # 1. Find user by email (username is used for email in OAuth2 form)
    user = session.exec(select(User).where(
        User.email == form_data.username)).first()

    # 2. Check if user exists and password is correct
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=400,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Generate the JWT
    access_token = create_access_token(data={"email": user.email})

    # 4. Return the token response
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/me", response_model=UserPublic, tags=["auth"])
def read_users_me(current_user: User = Depends(get_current_user)):
    """Returns the profile of the currently logged-in user (Task 3.2)."""
    return current_user


@app.get("/users/", response_model=List[UserPublic], tags=["users"])
def read_users(session: Session = Depends(get_session)):
    """Returns a list of all users."""
    users = session.exec(select(User)).all()
    return users


# =========================================================================
# --- Protected Post Routes (Task 3.3) ---
# =========================================================================

@app.post("/posts/", response_model=PostPublic, tags=["posts"])
def create_post(
    post: PostCreate,
    current_user: User = Depends(get_current_user),  # Protection added
    session: Session = Depends(get_session)
):
    """Creates a new post, setting the owner_id from the logged-in user (Task 3.3)."""

    # CRUCIAL: Set the owner_id from the authenticated user
    db_post = Post.model_validate(post, update={"owner_id": current_user.id})

    session.add(db_post)
    session.commit()
    session.refresh(db_post)
    return db_post


@app.get("/posts/", response_model=List[PostPublicWithOwner], tags=["posts"])
def read_posts(session: Session = Depends(get_session)):
    """Returns a list of all posts, including their owners."""
    posts = session.exec(select(Post)).all()
    return posts


@app.get("/posts/{post_id}", response_model=PostPublicWithComments, tags=["posts"])
def read_post(post_id: int, session: Session = Depends(get_session)):
    """Returns a single post by its ID, including its owner and comments."""
    post = session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@app.put("/posts/{post_id}", response_model=PostPublic, tags=["posts"])
def update_post(
    post_id: int,
    post_update: PostCreate,
    current_user: User = Depends(get_current_user),  # Protection added
    session: Session = Depends(get_session)
):
    """Updates an existing post. Only the owner should be allowed in a real app."""
    db_post = session.get(Post, post_id)
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Optional Authorization Check: Ensure the current user is the owner
    if db_post.owner_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this post")

    # Update the data, ensuring the owner_id remains the current user's ID
    update_data = post_update.model_dump(exclude_unset=True)
    update_data["owner_id"] = current_user.id  # Enforce owner integrity

    db_post.sqlmodel_update(update_data)

    session.add(db_post)
    session.commit()
    session.refresh(db_post)
    return db_post


@app.delete("/posts/{post_id}", tags=["posts"])
def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_user),  # Protection added
    session: Session = Depends(get_session)
):
    """Deletes a post. Only the owner should be allowed."""
    post = session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Optional Authorization Check: Ensure the current user is the owner
    if post.owner_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this post")

    session.delete(post)
    session.commit()
    return {"message": "Post deleted successfully"}


# =========================================================================
# --- Protected Comment Routes (Task 3.3) ---
# =========================================================================

@app.post("/posts/{post_id}/comments/", response_model=CommentPublic, tags=["comments"])
def create_comment(
    post_id: int,
    comment: CommentCreate,
    current_user: User = Depends(get_current_user),  # Protection added
    session: Session = Depends(get_session)
):
    """Creates a new comment, setting the owner_id from the logged-in user (Task 3.3)."""
    post = session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # CRUCIAL: Set the owner_id from the authenticated user
    db_comment = Comment.model_validate(
        comment,
        update={"post_id": post_id, "owner_id": current_user.id}
    )

    session.add(db_comment)
    session.commit()
    session.refresh(db_comment)
    return db_comment


@app.get("/posts/{post_id}/comments/", response_model=List[CommentPublicWithUser], tags=["comments"])
def read_comments_for_post(post_id: int, session: Session = Depends(get_session)):
    """Returns all comments for a specific post."""
    post = session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Access the comments relationship field
    return post.comments


@app.get("/comments/{comment_id}", response_model=CommentPublicWithUser, tags=["comments"])
def read_comment(comment_id: int, session: Session = Depends(get_session)):
    """Returns a single comment by its ID."""
    comment = session.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    return comment


@app.put("/comments/{comment_id}", response_model=CommentPublic, tags=["comments"])
def update_comment(
    comment_id: int,
    comment_update: CommentCreate,
    current_user: User = Depends(get_current_user),  # Protection added
    session: Session = Depends(get_session)
):
    """Updates an existing comment. Only the owner should be allowed."""
    db_comment = session.get(Comment, comment_id)
    if not db_comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Optional Authorization Check: Ensure the current user is the owner
    if db_comment.owner_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this comment")

    # Update the data, ensuring the owner_id remains the current user's ID
    update_data = comment_update.model_dump(exclude_unset=True)
    update_data["owner_id"] = current_user.id  # Enforce owner integrity

    db_comment.sqlmodel_update(update_data)

    session.add(db_comment)
    session.commit()
    session.refresh(db_comment)
    return db_comment


@app.delete("/comments/{comment_id}", tags=["comments"])
def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),  # Protection added
    session: Session = Depends(get_session)
):
    """Deletes a comment. Only the owner should be allowed."""
    comment = session.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Optional Authorization Check: Ensure the current user is the owner
    if comment.owner_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this comment")

    session.delete(comment)
    session.commit()
    return {"message": "Comment deleted successfully"}
