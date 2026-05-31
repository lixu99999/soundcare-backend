from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID


# User schemas
class UserPreferences(BaseModel):
    instrument: Optional[str] = "piano"
    ambient: Optional[str] = "rain"
    mix_ratio: Optional[int] = 30
    wake_time: Optional[str] = "07:00"
    sleep_time: Optional[str] = "23:00"


class UserCreate(BaseModel):
    nickname: Optional[str] = "SoundCare用户"


class UserResponse(BaseModel):
    id: UUID
    nickname: Optional[str]
    preferences: Dict[str, Any]
    sleep_time: Optional[str]
    wake_time: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# HRV data schemas
class HRVData(BaseModel):
    rmssd: int = Field(..., description="RMSSD value in ms")
    heart_rate: int = Field(..., description="Heart rate in BPM")
    sdnn: Optional[int] = Field(None, description="SDNN value in ms (Huawei Watch only)")
    pnn50: Optional[int] = Field(None, description="pNN50 value in % (Huawei Watch only)")
    rri_data: Optional[List[int]] = Field(None, description="Raw RRI data in ms (Huawei Watch only)")
    timestamp: Optional[datetime] = None


class HRVStatusEnum(str):
    RELAXED = "relaxed"  # >80ms
    NORMAL = "normal"  # 50-80ms
    STRESSED = "stressed"  # 30-50ms
    ANXIOUS = "anxious"  # <30ms


class MusicParameters(BaseModel):
    bpm: int = Field(..., description="Beats per minute")
    key: str = Field(..., description="Musical key, e.g., C_major")
    instrument: str = Field(..., description="Instrument: piano, strings, pad, nature")
    ambient: str = Field(..., description="Ambient sound: none, rain, ocean, forest")
    mix_ratio: Optional[int] = Field(30, description="Ambient mix ratio percentage")


class HRVAdjustment(BaseModel):
    target_bpm_reduction: int = Field(0, description="Suggested BPM reduction based on HRV")
    suggested_mood: str = Field("relaxing", description="Suggested mood: relaxing, calming, energizing")
    focus_low_freq: bool = Field(True, description="Whether to emphasize low frequencies")


# Music generation request/response
class MusicGenerateRequest(BaseModel):
    user_id: Optional[UUID] = None
    time_period: str = Field(..., description="Time period: morning_wake, morning_focus, noon_break, afternoon_focus, evening_relax, sleep")
    hrv_data: Optional[HRVData] = None
    hrv_status: Optional[str] = "normal"
    scene: Optional[str] = None
    preferences: Optional[MusicParameters] = None
    duration_minutes: int = Field(15, description="Duration in minutes")
    provider: Optional[str] = Field(None, description="Music provider: minimax or suno. If not set, uses DEFAULT_MUSIC_PROVIDER from config")
    optimized_prompt: Optional[str] = Field(None, description="LLM optimized prompt for music generation")


class MusicGenerateResponse(BaseModel):
    session_id: UUID
    music_url: str
    duration: Optional[int] = Field(None, description="音频实际时长（秒）")
    music_title: Optional[str] = Field(None, description="歌曲标题")
    cover_image_url: Optional[str] = Field(None, description="封面图URL")
    parameters: MusicParameters
    hrv_adjustment: HRVAdjustment
    healing_metrics: Dict[str, Any]


class HRVUpdateRequest(BaseModel):
    rmssd: int
    heart_rate: int
    elapsed_seconds: int
    device_type: str = Field(..., description="Device type: apple_watch, huawei_watch, polar")
    sdnn: Optional[int] = Field(None, description="SDNN value in ms (Huawei Watch only)")
    pnn50: Optional[int] = Field(None, description="pNN50 value in % (Huawei Watch only)")
    rri_data: Optional[List[int]] = Field(None, description="Raw RRI data in ms (Huawei Watch only)")


class HRVUpdateResponse(BaseModel):
    adjustment: Dict[str, Any]
    session_metrics: Dict[str, Any]


class HealingSessionResponse(BaseModel):
    id: UUID
    time_period: str
    scene: Optional[str]
    duration_minutes: int
    parameters: Dict[str, Any]
    healing_score: Optional[int]
    hrv_improve_percent: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# LLM Optimization schemas
class LLMOptimizeRequestSchema(BaseModel):
    user_input: str = Field(..., description="User's natural language input")
    time_period: str = Field(..., description="Current time period")
    hrv_status: Optional[str] = Field(None, description="HRV status if available")


class LLMOptimizeResponseSchema(BaseModel):
    scene: str = Field(..., description="Matched scene: sleep/relax/focus/meditate/study")
    optimized_prompt: str = Field(..., description="Optimized prompt for Suno")
    parameters: Dict[str, Any] = Field(..., description="Music parameters: bpm, key, instrument, ambient, mix_ratio")
    explanation: str = Field(..., description="LLM's explanation")


# MiniMax Music Generation schemas
class MiniMaxMusicGenerateRequest(BaseModel):
    prompt: str = Field(..., description="Music style description in Chinese or English")
    duration_ms: Optional[int] = Field(None, description="Duration preference in milliseconds")
    is_instrumental: bool = Field(True, description="Whether to generate instrumental music (no vocals)")
    output_format: str = Field("url", description="Output format: url or hex")


class MiniMaxMusicGenerateResponse(BaseModel):
    music_id: str
    status: int = Field(..., description="Music status: 0=processing, 1=processing, 2=completed")
    audio_url: Optional[str] = None
    duration_ms: Optional[int] = None
    message: str


class MiniMaxLyricsGenerateRequest(BaseModel):
    prompt: str = Field(..., description="Song theme/style description")
    title: Optional[str] = Field(None, description="Song title")


# Suno API schemas
class SunoMusicGenerateRequest(BaseModel):
    prompt: str = Field(..., description="Music style description")
    custom_mode: bool = Field(False, description="Whether to use custom mode")
    style: Optional[str] = Field(None, description="Style description (required for custom mode)")
    title: Optional[str] = Field(None, description="Song title")
    instrumental: bool = Field(True, description="Whether to generate instrumental music")
    model: str = Field("V5_5", description="Model version: V5_5/V5/V4_5/V4_5_2/V4")


class SunoMusicResponse(BaseModel):
    task_id: str
    status: str = Field(..., description="Task status: GENERATING/SUCCESS/FAILED/TIMEOUT")
    audio_url: Optional[str] = None
    video_url: Optional[str] = None
    title: Optional[str] = None
    duration: Optional[int] = None
    message: str


class SunoLyricsRequest(BaseModel):
    prompt: str = Field(..., description="Lyrics theme description")


class SunoLyricsResponse(BaseModel):
    task_id: str
    lyrics_list: List[Dict[str, str]] = Field(default_factory=list)
    message: str