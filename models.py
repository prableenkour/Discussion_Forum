from datetime import datetime
from flask_login import UserMixin
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship, declarative_base


Base = declarative_base()


class User(Base, UserMixin):
__tablename__ = 'users'
id = Column(Integer, primary_key=True)
username = Column(String(80), unique=True, nullable=False)
email = Column(String(120), unique=True, nullable=False)
password = Column(String(200), nullable=False)
created_at = Column(DateTime, default=datetime.utcnow)


threads = relationship('Thread', back_populates='author', cascade='all, delete-orphan')
posts = relationship('Post', back_populates='author', cascade='all, delete-orphan')


class Thread(Base):
__tablename__ = 'threads'
id = Column(Integer, primary_key=True)
title = Column(String(200), nullable=False)
body = Column(Text, nullable=False)
created_at = Column(DateTime, default=datetime.utcnow)
author_id = Column(Integer, ForeignKey('users.id'))


author = relationship('User', back_populates='threads')
posts = relationship('Post', back_populates='thread', cascade='all, delete-orphan')


class Post(Base):
__tablename__ = 'posts'
id = Column(Integer, primary_key=True)
body = Column(Text, nullable=False)
created_at = Column(DateTime, default=datetime.utcnow)
author_id = Column(Integer, ForeignKey('users.id'))
thread_id = Column(Integer, ForeignKey('threads.id'))


author = relationship('User', back_populates='posts')
thread = relationship('Thread', back_populates='posts')