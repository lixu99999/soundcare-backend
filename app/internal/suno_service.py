"""
Suno API Service - Suno 音乐生成 API 集成
支持疗愈音乐的纯音乐生成
"""

import os
import time
import requests
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

from app.core.config import settings


class SunoMusicGenerateRequest(BaseModel):
    """Suno 音乐生成请求"""
    prompt: str  # 音乐风格描述
    custom_mode: bool = False  # 是否使用自定义模式
    style: Optional[str] = None  # 风格描述（customMode=true时必填）
    title: Optional[str] = None  # 歌曲标题
    instrumental: bool = True  # 是否为纯音乐（必填）
    model: str = "V4_5ALL"  # 模型版本
    callback_url: Optional[str] = None  # 回调地址


class SunoMusicResult(BaseModel):
    """Suno 音乐生成结果"""
    task_id: str
    status: str  # TEXT_SUCCESS / PENDING / FAILED / TIMEOUT
    audio_url: Optional[str] = None
    title: Optional[str] = None
    duration: Optional[int] = None  # 秒
    image_url: Optional[str] = None  # 封面图URL
    message: str


class SunoLyricsRequest(BaseModel):
    """Suno 歌词生成请求"""
    prompt: str  # 歌词主题描述


class SunoLyricsResult(BaseModel):
    """Suno 歌词生成结果"""
    task_id: str
    lyrics_list: List[Dict[str, str]]  # [{title, text}, ...]
    message: str


class SunoService:
    """Suno API 音乐生成服务"""

    def __init__(self):
        self.base_url = "https://api.sunoapi.org/api/v1"
        self.api_key = settings.SUNO_API_KEY
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _check_api_key(self) -> bool:
        """检查 API Key 是否配置"""
        if not self.api_key:
            raise ValueError("SUNO_API_KEY 环境变量未设置")
        return True

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """发送请求的通用方法"""
        url = f"{self.base_url}{endpoint}"
        response = requests.request(method, url, headers=self._headers, **kwargs)
        result = response.json()

        if isinstance(result, dict) and result.get("code") != 200:
            raise Exception(f"Suno API 错误: {result.get('msg', '未知错误')}")

        return result

    def generate_music(self, request: SunoMusicGenerateRequest) -> SunoMusicResult:
        """
        生成疗愈音乐

        Args:
            request: 音乐生成请求

        Returns:
            SunoMusicResult: 包含 task_id 的响应（需要轮询获取结果）
        """
        self._check_api_key()

        payload = {
            "prompt": request.prompt,
            "customMode": request.custom_mode,
            "instrumental": request.instrumental,
            "model": request.model,
            "callBackUrl": request.callback_url or "https://example.com/callback"
        }

        if request.custom_mode:
            if request.style:
                payload["style"] = request.style
            if request.title:
                payload["title"] = request.title

        # 使用新端点 /api/v1/generate
        result = self._request("POST", "/generate", json=payload)
        task_id = result["data"]["taskId"]

        return SunoMusicResult(
            task_id=task_id,
            status="PENDING",
            message="音乐生成任务已创建，请轮询获取结果"
        )

    def get_music_status(self, task_id: str) -> Dict[str, Any]:
        """
        查询音乐生成状态

        Args:
            task_id: 任务ID

        Returns:
            状态信息字典
        """
        self._check_api_key()

        # 使用新端点 /api/v1/generate/record-info
        result = self._request(
            "GET",
            f"/generate/record-info?taskId={task_id}"
        )
        return result["data"]

    def wait_for_music(
        self,
        task_id: str,
        max_wait: int = 600,
        poll_interval: int = 30
    ) -> SunoMusicResult:
        """
        轮询等待音乐生成完成

        Args:
            task_id: 任务ID
            max_wait: 最大等待时间（秒）
            poll_interval: 轮询间隔（秒）

        Returns:
            SunoMusicResult: 包含音频URL的完成结果
        """
        start_time = time.time()

        while time.time() - start_time < max_wait:
            status_data = self.get_music_status(task_id)
            status = status_data.get("status")

            # 成功状态是 TEXT_SUCCESS
            if status == "TEXT_SUCCESS":
                suno_data = status_data.get("response", {}).get("sunoData", [])
                if suno_data:
                    audio_url = suno_data[0].get("streamAudioUrl") or suno_data[0].get("audioUrl")
                    return SunoMusicResult(
                        task_id=task_id,
                        status="TEXT_SUCCESS",
                        audio_url=audio_url,
                        title=suno_data[0].get("title"),
                        duration=suno_data[0].get("audioDuration"),
                        message="音乐生成成功",
                        image_url=suno_data[0].get("imageUrl")
                    )
                return SunoMusicResult(
                    task_id=task_id,
                    status="TEXT_SUCCESS",
                    message="音乐生成成功但无音频数据"
                )
            elif status == "FAILED":
                error_msg = status_data.get("errorMessage", "生成失败")
                return SunoMusicResult(
                    task_id=task_id,
                    status="FAILED",
                    message=f"生成失败: {error_msg}"
                )

            time.sleep(poll_interval)

        return SunoMusicResult(
            task_id=task_id,
            status="TIMEOUT",
            message="音乐生成超时"
        )

    def generate_music_with_wait(
        self,
        request: SunoMusicGenerateRequest,
        max_wait: int = 120
    ) -> SunoMusicResult:
        """
        生成音乐并等待完成（一步完成）

        Args:
            request: 音乐生成请求
            max_wait: 最大等待时间

        Returns:
            SunoMusicResult: 包含音频URL的完成结果
        """
        result = self.generate_music(request)
        return self.wait_for_music(result.task_id, max_wait)

    def generate_lyrics(self, request: SunoLyricsRequest) -> SunoLyricsResult:
        """
        生成歌词

        Args:
            request: 歌词生成请求

        Returns:
            SunoLyricsResult: 包含 task_id 的响应
        """
        self._check_api_key()

        result = self._request(
            "POST",
            "/generate/lyrics",
            json={"prompt": request.prompt}
        )
        task_id = result["data"]["taskId"]

        return SunoLyricsResult(
            task_id=task_id,
            lyrics_list=[],
            message="歌词生成任务已创建，请轮询获取结果"
        )

    def get_lyrics_status(self, task_id: str) -> Dict[str, Any]:
        """
        查询歌词生成状态

        Args:
            task_id: 任务ID

        Returns:
            状态信息字典
        """
        self._check_api_key()

        result = self._request(
            "GET",
            f"/lyrics/record-info?taskId={task_id}"
        )
        return result["data"]

    def wait_for_lyrics(
        self,
        task_id: str,
        max_wait: int = 300,
        poll_interval: int = 20
    ) -> SunoLyricsResult:
        """
        轮询等待歌词生成完成

        Args:
            task_id: 任务ID
            max_wait: 最大等待时间（秒）
            poll_interval: 轮询间隔（秒）

        Returns:
            SunoLyricsResult: 包含歌词的完成结果
        """
        start_time = time.time()

        while time.time() - start_time < max_wait:
            status_data = self.get_lyrics_status(task_id)
            success_flag = status_data.get("successFlag")

            if success_flag == "SUCCESS":
                lyrics_list = status_data.get("response", {}).get("data", [])
                return SunoLyricsResult(
                    task_id=task_id,
                    lyrics_list=lyrics_list,
                    message="歌词生成成功"
                )
            elif success_flag in ("CREATE_TASK_FAILED", "GENERATE_LYRICS_FAILED"):
                error_msg = status_data.get("errorMessage", "生成失败")
                return SunoLyricsResult(
                    task_id=task_id,
                    lyrics_list=[],
                    message=f"生成失败: {error_msg}"
                )
            elif success_flag == "SENSITIVE_WORD_ERROR":
                return SunoLyricsResult(
                    task_id=task_id,
                    lyrics_list=[],
                    message="歌词生成失败：包含敏感词"
                )

            time.sleep(poll_interval)

        return SunoLyricsResult(
            task_id=task_id,
            lyrics_list=[],
            message="歌词生成超时"
        )

    def get_credits(self) -> int:
        """
        查询账户剩余积分

        Returns:
            剩余积分数量
        """
        self._check_api_key()

        try:
            result = self._request("GET", "/generate/credit")
            data = result.get("data", 0)
            return int(data) if isinstance(data, (int, float)) else 0
        except Exception as e:
            print(f"查询积分失败: {e}")
            return 0


# 全局单例
suno_service = SunoService()