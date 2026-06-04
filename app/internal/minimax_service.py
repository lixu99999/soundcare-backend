"""
Music Generation Service - MiniMax 音乐生成 API 集成
支持疗愈音乐的纯音乐生成
"""

import os
import requests
from typing import Optional, Dict, Any
from pydantic import BaseModel

from app.core.config import settings


class MiniMaxApiRequest(BaseModel):
    """MiniMax API请求（内部使用）"""
    prompt: str
    duration_ms: Optional[int] = None
    is_instrumental: bool = True
    output_format: str = "url"


class MiniMaxMusicGenerationResponse(BaseModel):
    """MiniMax音乐生成响应"""
    music_id: str
    status: int  # 0=处理中, 1=处理中, 2=已完成
    audio_url: Optional[str] = None
    duration_ms: Optional[int] = None
    message: str


class MiniMaxLyricsGenerationRequest(BaseModel):
    """MiniMax歌词生成请求"""
    prompt: str
    title: Optional[str] = None


class MiniMaxLyricsGenerationResponse(BaseModel):
    """MiniMax歌词生成响应"""
    song_title: str
    style_tags: str
    lyrics: str


class MiniMaxService:
    """MiniMax音乐生成服务"""

    def __init__(self):
        self.base_url = "https://api.minimaxi.com"
        self.api_key = settings.MINIMAX_API_KEY
        self.model = "music-2.6"
        self.free_model = "music-2.6-free"

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def _check_api_key(self) -> bool:
        """检查 API Key 是否配置"""
        if not self.api_key:
            raise ValueError("MINIMAX_API_KEY 环境变量未设置")
        return True

    async def generate_music(
        self,
        request: MiniMaxApiRequest
    ) -> MiniMaxMusicGenerationResponse:
        """
        生成疗愈音乐（纯音乐）

        Args:
            request: MiniMaxApiRequest

        Returns:
            MiniMaxMusicGenerationResponse: 包含音频URL的响应
        """
        self._check_api_key()

        url = f"{self.base_url}/v1/music_generation"

        payload = {
            "model": self.model,
            "prompt": request.prompt,
            "is_instrumental": request.is_instrumental,
            "audio_setting": {
                "sample_rate": 44100,
                "bitrate": 256000,
                "format": "mp3"
            },
            "output_format": request.output_format
        }

        try:
            response = requests.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=300  # 音乐生成可能需要较长时间
            )
            result = response.json()

            if result.get("base_resp", {}).get("status_code") != 0:
                error_msg = result.get("base_resp", {}).get("status_msg", "未知错误")
                raise Exception(f"MiniMax API 错误: {error_msg}")

            data = result.get("data", {})
            extra_info = result.get("extra_info", {})

            return MiniMaxMusicGenerationResponse(
                music_id=data.get("music_id", ""),
                status=data.get("status", 0),
                audio_url=data.get("audio"),
                duration_ms=extra_info.get("music_duration"),
                message="音乐生成成功" if data.get("status") == 2 else "音乐生成中"
            )

        except requests.RequestException as e:
            raise Exception(f"音乐生成请求失败: {str(e)}")

    async def generate_music_with_lyrics(
        self,
        prompt: str,
        lyrics: str,
        title: Optional[str] = None
    ) -> MiniMaxMusicGenerationResponse:
        """
        生成带歌词的音乐

        Args:
            prompt: 音乐风格描述
            lyrics: 歌词（\n分隔）
            title: 歌曲标题

        Returns:
            MiniMaxMusicGenerationResponse
        """
        self._check_api_key()

        url = f"{self.base_url}/v1/music_generation"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "lyrics": lyrics,
            "audio_setting": {
                "sample_rate": 44100,
                "bitrate": 256000,
                "format": "mp3"
            },
            "output_format": "url"
        }

        try:
            response = requests.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=300  # 音乐生成可能需要较长时间
            )
            result = response.json()

            if result.get("base_resp", {}).get("status_code") != 0:
                error_msg = result.get("base_resp", {}).get("status_msg", "未知错误")
                raise Exception(f"MiniMax API 错误: {error_msg}")

            data = result.get("data", {})
            extra_info = result.get("extra_info", {})

            return MiniMaxMusicGenerationResponse(
                music_id=data.get("music_id", ""),
                status=data.get("status", 0),
                audio_url=data.get("audio"),
                duration_ms=extra_info.get("music_duration"),
                message="音乐生成成功" if data.get("status") == 2 else "音乐生成中"
            )

        except requests.RequestException as e:
            raise Exception(f"音乐生成请求失败: {str(e)}")

    async def generate_lyrics(
        self,
        request: MiniMaxLyricsGenerationRequest
    ) -> MiniMaxLyricsGenerationResponse:
        """
        生成歌词

        Args:
            request: MiniMaxLyricsGenerationRequest

        Returns:
            MiniMaxLyricsGenerationResponse: 包含歌词的响应
        """
        self._check_api_key()

        url = f"{self.base_url}/v1/lyrics_generation"

        payload = {
            "mode": "write_full_song",
            "prompt": request.prompt
        }
        if request.title:
            payload["title"] = request.title

        try:
            response = requests.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=30
            )
            result = response.json()

            if result.get("base_resp", {}).get("status_code") != 0:
                error_msg = result.get("base_resp", {}).get("status_msg", "未知错误")
                raise Exception(f"MiniMax API 错误: {error_msg}")

            return MiniMaxLyricsGenerationResponse(
                song_title=result.get("song_title", ""),
                style_tags=result.get("style_tags", ""),
                lyrics=result.get("lyrics", "")
            )

        except requests.RequestException as e:
            raise Exception(f"歌词生成请求失败: {str(e)}")

    async def get_music_status(self, music_id: str) -> Dict[str, Any]:
        """
        查询音乐生成状态（用于轮询）

        Args:
            music_id: 音乐ID

        Returns:
            状态信息字典
        """
        return {
            "music_id": music_id,
            "status": 0,
            "message": "请使用返回的 music_id 进行后续查询"
        }


minimax_service = MiniMaxService()