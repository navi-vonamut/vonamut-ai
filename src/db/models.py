import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Float
from sqlalchemy.orm import declarative_base, relationship
from src.db.base import Base

Base = declarative_base()

class Post(Base):
    __tablename__ = 'posts'
    
    id = Column(Integer, primary_key=True)
    region = Column(String(50), nullable=False)   # LATAM, US, RU и т.д.
    platform = Column(String(50), nullable=False) # IG, FB
    theme = Column(String(255))
    content = Column(Text, nullable=False)
    image_url = Column(String(512))
    status = Column(String(50), default='DRAFT')  # DRAFT, PUBLISHED
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    scheduled_at = Column(DateTime)

class Milestone(Base):
    __tablename__ = 'milestones'
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    status = Column(String(50)) # Planned, In Progress, Completed
    deadline = Column(DateTime)

class Task(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(50), default='BACKLOG')
    priority = Column(String(50))
    assignee = Column(String(50)) # 🔥 Кто должен сделать
    agent_report = Column(Text)   # 🔥 Отчет о проделанной работе
    milestone = Column(Integer, ForeignKey('milestones.id'))

class InstagramLead(Base):
    __tablename__ = 'instagram_leads'
    id = Column(Integer, primary_key=True)
    username = Column(String(100), nullable=False)
    intent_score = Column(String(50), default='MEDIUM') # HIGH, MEDIUM, LOW
    interests = Column(Text)
    status = Column(String(50), default='NEW') # NEW, CONTACTED, IN_CONVERSATION, CONVERTED
    last_comment = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)

class InstagramConversation(Base):
    __tablename__ = 'instagram_conversations'
    id = Column(Integer, primary_key=True)
    username = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False) # 'user' or 'twin'
    message_text = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class SportsMatch(Base):
    __tablename__ = 'sports_matches'
    
    id = Column(Integer, primary_key=True)
    match_id = Column(String(100), unique=True, index=True, nullable=False) # External ID from The-Odds-API
    league = Column(String(100), nullable=False)
    team1 = Column(String(150), nullable=False)
    team2 = Column(String(150), nullable=False)
    commence_time = Column(DateTime, nullable=False)
    status = Column(String(50), default='SCHEDULED') # SCHEDULED, FINISHED, CANCELLED
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class SportsOdds(Base):
    __tablename__ = 'sports_odds'
    
    id = Column(Integer, primary_key=True)
    match_id = Column(String(100), ForeignKey('sports_matches.match_id'), nullable=False)
    bookmaker = Column(String(100), default='pinnacle') # e.g. pinnacle
    odds_team1 = Column(Float, nullable=False)
    odds_draw = Column(Float, nullable=True) # None for sports like ice hockey / basketball without 2-way draw
    odds_team2 = Column(Float, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)

class SportsBet(Base):
    __tablename__ = 'sports_bets'
    
    id = Column(Integer, primary_key=True)
    match_id = Column(String(100), nullable=False)
    league = Column(String(100), nullable=False)
    team1 = Column(String(150), nullable=False)
    team2 = Column(String(150), nullable=False)
    bet_target = Column(String(50), nullable=False) # "Победа 1", "Ничья", "Победа 2"
    bookmaker_odds = Column(Float, nullable=False)
    ai_probability = Column(Float, nullable=False) # e.g. 0.48 for 48%
    value_percentage = Column(Float, nullable=False) # e.g. 0.17 for +17%
    ai_reasoning = Column(Text, nullable=True)
    user_action = Column(String(50), default='PENDING') # PENDING, PLACED, SKIPPED
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
