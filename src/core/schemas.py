from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

# Строго задаем возможные статусы воронки
class LeadStatus(str, Enum):
    commented = "commented"
    followed_back = "followed_back"
    dm_sent = "dm_sent"
    registered = "registered"

# Строго задаем поддерживаемые площадки
class SocialNetwork(str, Enum):
    instagram = "instagram"
    threads = "threads"
    telegram = "telegram"
    vk = "vk"
    x = "x"

class SMMLead(BaseModel):
    id: Optional[str] = Field(default=None, description="UUID записи в Directus")
    
    # Трекинг источника
    social_network: SocialNetwork = Field(default=SocialNetwork.instagram)
    source_tag: Optional[str] = Field(default=None, description="Например: #самопознание")
    lead_username: str = Field(..., description="Никнейм или ID лида")
    
    # История взаимодействий
    target_post_url: Optional[str] = Field(default=None, description="Ссылка на пост лида")
    our_comment: Optional[str] = Field(default=None, description="Текст нашего комментария")
    dm_message: Optional[str] = Field(default=None, description="Текст отправленного в Директ приветствия")
    
    # Конверсионные элементы
    promo_code: Optional[str] = Field(default=None, description="Сгенерированный промокод, например IG-IVAN-A1B2")
    utm_link: Optional[str] = Field(default=None, description="UTM-ссылка на AstroGuido")
    status: LeadStatus = Field(default=LeadStatus.commented)
