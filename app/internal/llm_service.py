"""
LLM Service - 使用LLM理解用户意图并生成优化的音乐生成prompt
支持 OpenAI兼容API / Google Gemini
"""

import os
import json
import re
from typing import Optional
from pydantic import BaseModel

from app.core.config import settings


class LLMOptimizeRequest(BaseModel):
    user_input: str  # 用户自然语言输入
    time_period: str  # 当前时间段
    hrv_status: Optional[str] = None  # HRV状态（如果可用）


class LLMOptimizeResponse(BaseModel):
    scene: str
    optimized_prompt: str
    parameters: dict
    explanation: str


SCENE_CONFIGS = {
    "sleep": {"bpm_range": (50, 65), "key": "A小调", "instrument": "钢琴+弦乐", "ambient": "雨声", "mix_ratio": 25, "mood": "平静、引导入睡、渐弱结束"},
    "relax": {"bpm_range": (60, 75), "key": "C大调", "instrument": "钢琴+电子Pad", "ambient": "自然音", "mix_ratio": 30, "mood": "放松、舒缓"},
    "focus": {"bpm_range": (75, 95), "key": "C大调", "instrument": "钢琴独奏", "ambient": "无", "mix_ratio": 0, "mood": "专注、稳定"},
    "meditate": {"bpm_range": (40, 60), "key": "全音阶", "instrument": "Pad合成器", "ambient": "森林或海浪", "mix_ratio": 35, "mood": "空灵、冥想"},
    "study": {"bpm_range": (70, 90), "key": "C大调", "instrument": "钢琴或古典吉他", "ambient": "轻微白噪音", "mix_ratio": 20, "mood": "清晰、专注"},
}


class LLMService:
    def __init__(self):
        self.provider = settings.LLM_PROVIDER.lower()
        self.api_key = settings.GEMINI_API_KEY if self.provider == "gemini" else settings.MINIMAX_API_KEY

    def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
        from openai import OpenAI
        client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.minimaxi.com/v1"
        )
        response = client.chat.completions.create(
            model="MiniMax-M2.7",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1024
        )
        return response.choices[0].message.content

    def _call_gemini(self, system_prompt: str, user_prompt: str) -> str:
        from google.genai import Client
        client = Client(api_key=self.api_key)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"{system_prompt}\n\n{user_prompt}"
        )
        return response.text

    def _build_system_prompt(self) -> str:
        return """You are a professional Suno AI music prompt engineer. Your task is to transform user's natural language input into detailed, optimized prompts specifically designed for Suno AI music generation.

## Important Context
- This prompt will be used directly with Suno AI music generation API
- Suno works best with clear, structured prompts in English
- Include specific musical instructions (BPM, instruments, scale, etc.)
- Add ambient sounds that enhance the desired mood

## Output Format
Return a JSON object with these fields:
- scene: Scene type (creative description based on user input)
- optimized_prompt: Detailed English prompt for Suno (see example below)
- parameters: Object with bpm, key, instrument, ambient, mix_ratio
- explanation: Brief explanation in Chinese

## Prompt Structure Example
Create a [duration]-minute healing audio for [user's scenario]:

MELODY:
- Tempo (BPM 60-85), [instrument description]
- Frequencies: [frequency range description], avoid [what to avoid]
- Scale: [musical scale for desired mood]

AMBIENT LAYER:
- [Ambient sound description]
- [How ambient enhances the mood]
- Volume: [X]% of total mix

TEMPORAL STRUCTURE:
- 0:00-[X]: [Opening description]
- [X]:[X]-[X]: [Main body description]
- [X]:[X]-[X]: [Ending description]

MIX: Stereo, 44.1kHz, [music_percentage]% music / [ambient_percentage]% ambient

## Requirements
1. Output in English only for optimized_prompt (Suno requirement)
2. Be creative and specific - describe melody, harmony, rhythm, timbre
3. Include temporal structure with timestamps
4. Specify frequency ranges for healing effect
5. Match BPM to user's scenario and desired mood
6. Add appropriate ambient sounds to enhance immersion
7. Return ONLY JSON, no markdown formatting"""

    def _build_user_prompt(self, request: LLMOptimizeRequest) -> str:
        return f"用户输入：{request.user_input}"

    def _parse_response(self, response: str) -> dict:
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return self._fallback_parse(response)

    def _fallback_parse(self, user_input: str) -> dict:
        user_lower = user_input.lower()
        if any(k in user_lower for k in ['睡', '晚', '夜', '困']):
            scene = 'sleep'
        elif any(k in user_lower for k in ['累', '压力', '放松', '舒缓', '休息']):
            scene = 'relax'
        elif any(k in user_lower for k in ['专注', '考试', '工作', '学习', '读书']):
            scene = 'focus'
        elif any(k in user_lower for k in ['冥想', '禅', '静心']):
            scene = 'meditate'
        else:
            scene = 'study'

        config = SCENE_CONFIGS[scene]
        bpm = (config['bpm_range'][0] + config['bpm_range'][1]) // 2
        return {
            "scene": scene,
            "optimized_prompt": f"A {bpm} BPM healing music, {config['mood']}, {config['instrument'].lower()}",
            "parameters": {"bpm": bpm, "key": config['key'], "instrument": config['instrument'], "ambient": config['ambient'], "mix_ratio": config['mix_ratio']},
            "explanation": f"匹配到【{scene}】场景"
        }

    async def optimize(self, request: LLMOptimizeRequest) -> LLMOptimizeResponse:
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(request)

        try:
            if not self.api_key:
                parsed = self._fallback_parse(request.user_input)
                return LLMOptimizeResponse(**parsed)

            if self.provider == "gemini":
                llm_response = self._call_gemini(system_prompt, user_prompt)
            else:
                llm_response = self._call_openai(system_prompt, user_prompt)

            parsed = self._parse_response(llm_response)
            return LLMOptimizeResponse(**parsed)
        except Exception as e:
            print(f"LLM调用失败: {e}")
            parsed = self._fallback_parse(request.user_input)
            return LLMOptimizeResponse(**parsed)


llm_service = LLMService()