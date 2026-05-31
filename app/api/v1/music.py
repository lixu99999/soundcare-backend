from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional
import uuid

from app.core.database import get_db
from app.models.models import User, HealingSession, HRVRecord
from app.schemas.schemas import (
    MusicGenerateRequest,
    MusicGenerateResponse,
    HRVUpdateRequest,
    HRVUpdateResponse,
    MusicParameters,
    HRVAdjustment,
    UserCreate,
    UserResponse,
    HealingSessionResponse,
    MiniMaxMusicGenerateRequest,
    MiniMaxMusicGenerateResponse,
    MiniMaxLyricsGenerateRequest,
    SunoMusicGenerateRequest,
    SunoMusicResponse,
    SunoLyricsRequest,
    SunoLyricsResponse,
)
from app.internal.llm_service import llm_service, LLMOptimizeRequest
from app.internal.hrv_service import hrv_service, HRVMetrics, HRVStatus
from app.internal.minimax_service import minimax_service, MiniMaxApiRequest as MiniMaxRequest
from app.internal.suno_service import suno_service, SunoMusicGenerateRequest as SunoRequest
from app.core.config import settings

router = APIRouter(prefix="/music", tags=["music"])


@router.post("/llm-optimize")
async def llm_optimize_prompt(request: dict, db: Session = Depends(get_db)):
    """
    使用LLM理解用户输入，生成优化的Suno prompt
    这是产品的重要功能点：自然语言 → AI理解 → 优化prompt → 生成音乐
    """
    user_input = request.get("user_input", "")
    time_period = request.get("time_period", "evening_relax")
    hrv_status = request.get("hrv_status")

    if not user_input:
        raise HTTPException(status_code=400, detail="user_input is required")

    # 调用LLM服务优化prompt
    llm_request = LLMOptimizeRequest(
        user_input=user_input,
        time_period=time_period,
        hrv_status=hrv_status
    )

    result = await llm_service.optimize(llm_request)

    return {
        "scene": result.scene,
        "optimized_prompt": result.optimized_prompt,
        "parameters": result.parameters,
        "explanation": result.explanation
    }


@router.post("/generate", response_model=MusicGenerateResponse)
async def generate_music(request: MusicGenerateRequest, db: Session = Depends(get_db)):
    """
    Generate healing music based on time period, HRV data, and preferences.
    Provider is determined by request.provider or DEFAULT_MUSIC_PROVIDER from config.
    """
    print(f"收到 /generate 请求: {request}")
    print(f"optimized_prompt: {request.optimized_prompt}")
    print(f"preferences: {request.preferences}")

    # Determine provider
    provider = request.provider or settings.DEFAULT_MUSIC_PROVIDER

    # Determine BPM based on time period and HRV
    time_period_bpm = {
        "morning_wake": 80,
        "morning_focus": 85,
        "noon_break": 70,
        "afternoon_focus": 85,
        "evening_relax": 65,
        "sleep": 55,
    }

    base_bpm = time_period_bpm.get(request.time_period, 70)
    current_bpm = base_bpm

    # Adjust BPM based on HRV if provided
    hrv_adjustment = HRVAdjustment()
    if request.hrv_data:
        hrv_metrics = HRVMetrics(
            rmssd=request.hrv_data.rmssd,
            sdnn=request.hrv_data.sdnn or request.hrv_data.rmssd,
            pnn50=request.hrv_data.pnn50 or 0,
            heart_rate=request.hrv_data.heart_rate
        )
        hrv_status = hrv_service.determine_status(hrv_metrics)
        bpm_delta, target_bpm = hrv_service.calculate_bpm_adjustment(hrv_status, base_bpm)

        current_bpm = target_bpm

        hrv_adjustment = HRVAdjustment(
            target_bpm_reduction=abs(bpm_delta),
            suggested_mood=hrv_status.status,
            focus_low_freq=hrv_status.level >= 3,
        )

    # Use provided parameters or defaults
    parameters = request.preferences or MusicParameters(
        bpm=current_bpm,
        key="C_major",
        instrument="piano",
        ambient="rain",
        mix_ratio=30,
    )

    # Use optimized_prompt from LLM if available, otherwise build from parameters
    if request.optimized_prompt and request.optimized_prompt.strip():
        prompt = request.optimized_prompt
        print(f"[DEBUG] 使用LLM优化的prompt: {prompt}")
    else:
        # Build prompt from parameters - include BPM for better music generation
        prompt = f"A {parameters.bpm} BPM healing music, {parameters.instrument.lower()}, {parameters.ambient}"
        print(f"[DEBUG] 使用参数构建的prompt: {prompt}")

    print(f"[DEBUG] 最终发送给Suno的prompt: {prompt}")

    session_id = uuid.uuid4()
    music_url = None

    # Call music generation service based on provider
    duration = None
    music_title = None
    cover_image_url = None
    if provider == "suno":
        try:
            # If optimized_prompt is provided (from LLM), use custom_mode for longer prompts
            if request.optimized_prompt and request.optimized_prompt.strip():
                suno_request = SunoRequest(
                    prompt=prompt,
                    instrumental=True,
                    custom_mode=True,
                    style="healing music, relaxing, calming"
                )
            else:
                suno_request = SunoRequest(
                    prompt=prompt,
                    instrumental=True
                )
            result = suno_service.generate_music_with_wait(suno_request)
            music_url = result.audio_url
            # Suno不返回duration时，用请求的duration_minutes估算
            duration = result.duration or (request.duration_minutes * 60)
            music_title = result.title
            cover_image_url = result.image_url
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Suno generation failed: {str(e)}")
    else:
        # Default to MiniMax
        try:
            minimax_request = MiniMaxRequest(
                prompt=prompt,
                is_instrumental=True
            )
            result = await minimax_service.generate_music(minimax_request)
            music_url = result.audio_url
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"MiniMax generation failed: {str(e)}")

    response = MusicGenerateResponse(
        session_id=session_id,
        music_url=music_url or f"https://cdn.soundcare.com/music/{session_id}.mp3",
        duration=duration,
        music_title=music_title,
        cover_image_url=cover_image_url,
        parameters=parameters,
        hrv_adjustment=hrv_adjustment,
        healing_metrics={
            "hrv_sync_index": 85,
            "rhythm_sync_index": 88,
            "relaxation_potential": 82,
        },
    )

    return response


@router.post("/session/{session_id}/hrv-update", response_model=HRVUpdateResponse)
async def update_hrv(
    session_id: UUID,
    request: HRVUpdateRequest,
    db: Session = Depends(get_db),
):
    """
    Update HRV data during playback and get music parameter adjustments.
    Uses HRVService for accurate HRV status determination and BPM calculation.

    Device handling:
    - apple_watch: Receives heart rate sequences, estimates HRV (precision limited)
    - huawei_watch: Receives raw RRI data, calculates precise HRV metrics
    - polar: Receives raw RRI data, calculates precise HRV metrics (most accurate)
    """
    # Calculate HRV metrics based on device type
    if request.device_type == "huawei_watch" and request.rri_data:
        # Huawei Watch / Polar: Raw RRI data available, calculate precise HRV
        hrv_metrics = hrv_service.calculate_metrics_from_rri(request.rri_data)
        hrv_metrics.heart_rate = request.heart_rate
    else:
        # Apple Watch: Only heart rate available, estimate HRV
        # In production, would accumulate heart rate samples over time
        hrv_metrics = HRVMetrics(
            rmssd=request.rmssd,
            sdnn=request.sdnn or request.rmssd,
            pnn50=request.pnn50 or 0,
            heart_rate=request.heart_rate
        )

    # Determine HRV status using HRVService
    hrv_status = hrv_service.determine_status(hrv_metrics)

    # Calculate BPM adjustment
    bpm_delta, target_bpm = hrv_service.calculate_bpm_adjustment(hrv_status, 70)

    # Calculate healing progress (would need session's initial HRV in production)
    healing_progress = hrv_service.calculate_healing_progress(
        initial_hrv=30,
        current_hrv=hrv_metrics.rmssd,
        target_hrv=65
    )

    return HRVUpdateResponse(
        adjustment={
            "bpm_delta": bpm_delta,
            "next_segment_params": {
                "bpm": target_bpm,
                "suggested_mood": hrv_status.description,
                "focus_low_freq": hrv_status.level >= 3,
            },
        },
        session_metrics={
            "hrv_trend": f"{'+' if request.rmssd > 30 else ''}{request.rmssd - 30}ms",
            "healing_progress": healing_progress,
        },
    )


@router.get("/sessions/{user_id}", response_model=list[HealingSessionResponse])
async def get_user_sessions(user_id: UUID, db: Session = Depends(get_db)):
    """
    Get all healing sessions for a user.
    """
    sessions = (
        db.query(HealingSession)
        .filter(HealingSession.user_id == user_id)
        .order_by(HealingSession.created_at.desc())
        .limit(20)
        .all()
    )
    return sessions


# ============ MiniMax Music Generation APIs ============

@router.post("/minimax/generate", response_model=MiniMaxMusicGenerateResponse)
async def generate_music_minimax(request: MiniMaxMusicGenerateRequest):
    """
    Generate healing music using MiniMax API.
    This is the core music generation endpoint for SoundCare.
    """
    music_request = MiniMaxRequest(
        prompt=request.prompt,
        duration_ms=request.duration_ms,
        is_instrumental=request.is_instrumental,
        output_format=request.output_format
    )

    result = await minimax_service.generate_music(music_request)

    return MiniMaxMusicGenerateResponse(
        music_id=result.music_id,
        status=result.status,
        audio_url=result.audio_url,
        duration_ms=result.duration_ms,
        message=result.message
    )


@router.post("/minimax/generate-with-lyrics")
async def generate_music_with_lyrics(
    prompt: str,
    lyrics: str,
    title: Optional[str] = None
):
    """
    Generate music with lyrics using MiniMax API.
    Used for healing music that includes guided breathing or affirmations.
    """
    result = await minimax_service.generate_music_with_lyrics(prompt, lyrics, title)

    return {
        "music_id": result.music_id,
        "status": result.status,
        "audio_url": result.audio_url,
        "duration_ms": result.duration_ms,
        "message": result.message
    }


@router.post("/minimax/lyrics", response_model=dict)
async def generate_lyrics_minimax(request: MiniMaxLyricsGenerateRequest):
    """
    Generate lyrics for healing music using MiniMax API.
    First generates lyrics, then use /minimax/generate-with-lyrics to create the music.
    """
    lyrics_result = await minimax_service.generate_lyrics(request)

    return {
        "song_title": lyrics_result.song_title,
        "style_tags": lyrics_result.style_tags,
        "lyrics": lyrics_result.lyrics
    }


# ============ Suno API Endpoints ============

@router.post("/suno/generate", response_model=SunoMusicResponse)
async def generate_music_suno(request: SunoMusicGenerateRequest):
    """
    Generate healing music using Suno API.
    Returns task_id for polling status via /suno/status/{task_id}
    """
    result = suno_service.generate_music(request)

    return SunoMusicResponse(
        task_id=result.task_id,
        status=result.status,
        audio_url=result.audio_url,
        video_url=result.video_url,
        title=result.title,
        duration=result.duration,
        message=result.message
    )


@router.get("/suno/status/{task_id}", response_model=SunoMusicResponse)
async def get_suno_music_status(task_id: str):
    """
    Query Suno music generation status by task_id.
    Use this endpoint to poll for music generation completion.
    """
    status_data = suno_service.get_music_status(task_id)
    status = status_data.get("status")

    if status == "SUCCESS":
        audio_list = status_data.get("response", {}).get("data", [])
        audio = audio_list[0] if audio_list else {}
        return SunoMusicResponse(
            task_id=task_id,
            status="SUCCESS",
            audio_url=audio.get("audio_url"),
            video_url=audio.get("video_url"),
            title=audio.get("title"),
            duration=audio.get("duration"),
            message="Music generation completed"
        )
    elif status == "FAILED":
        return SunoMusicResponse(
            task_id=task_id,
            status="FAILED",
            message=f"Generation failed: {status_data.get('errorMessage', 'Unknown error')}"
        )
    else:
        return SunoMusicResponse(
            task_id=task_id,
            status="GENERATING",
            message="Music generation in progress"
        )


@router.post("/suno/generate-with-wait", response_model=SunoMusicResponse)
async def generate_music_suno_with_wait(request: SunoMusicGenerateRequest):
    """
    Generate music using Suno API and wait for completion.
    Note: This may take several minutes. Consider using /suno/generate instead.
    """
    result = suno_service.generate_music_with_wait(request)

    return SunoMusicResponse(
        task_id=result.task_id,
        status=result.status,
        audio_url=result.audio_url,
        video_url=result.video_url,
        title=result.title,
        duration=result.duration,
        message=result.message
    )


@router.post("/suno/lyrics", response_model=SunoLyricsResponse)
async def generate_lyrics_suno(request: SunoLyricsRequest):
    """
    Generate lyrics using Suno API.
    Returns task_id for polling status via /suno/lyrics-status/{task_id}
    """
    result = suno_service.generate_lyrics(request)

    return SunoLyricsResponse(
        task_id=result.task_id,
        lyrics_list=result.lyrics_list,
        message=result.message
    )


@router.get("/suno/lyrics-status/{task_id}", response_model=SunoLyricsResponse)
async def get_suno_lyrics_status(task_id: str):
    """
    Query Suno lyrics generation status by task_id.
    """
    status_data = suno_service.get_lyrics_status(task_id)
    success_flag = status_data.get("successFlag")

    if success_flag == "SUCCESS":
        lyrics_list = status_data.get("response", {}).get("data", [])
        return SunoLyricsResponse(
            task_id=task_id,
            lyrics_list=lyrics_list,
            message="Lyrics generation completed"
        )
    elif success_flag in ("CREATE_TASK_FAILED", "GENERATE_LYRICS_FAILED"):
        return SunoLyricsResponse(
            task_id=task_id,
            lyrics_list=[],
            message=f"Generation failed: {status_data.get('errorMessage', 'Unknown error')}"
        )
    elif success_flag == "SENSITIVE_WORD_ERROR":
        return SunoLyricsResponse(
            task_id=task_id,
            lyrics_list=[],
            message="Generation failed: sensitive word detected"
        )
    else:
        return SunoLyricsResponse(
            task_id=task_id,
            lyrics_list=[],
            message="Lyrics generation in progress"
        )


@router.get("/suno/credits")
async def get_suno_credits():
    """
    Query Suno API account remaining credits.
    """
    credits = suno_service.get_credits()
    return {"credits": credits}