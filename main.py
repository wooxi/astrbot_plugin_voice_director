import os
import re
import json
import random
import aiohttp
from pathlib import Path
from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.message_components import Plain, Record, Image, At, Json
from astrbot.api import logger
from astrbot.api.star import Context, Star, register

@register("voice_director", "wooxi", "多角色自适应专属音色分发与智能语音导演插件（支持BreezeBlue克隆音色）", "v1.2.0")
class VoiceDirectorPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.context = context
        self.config = config or {}
        
        self.engine = self.config.get("engine", "breezeblue")
        self.breeze_api_key = self.config.get("breeze_api_key", "brz_RIpSj5DDMmsx7EHzVjPXisRK2BkWTgbi").strip()
        
        # 专属 Voice ID
        self.linwan_voice_id = self.config.get("linwan_voice_id", "voc_yu7t5b4tx7c7")
        self.linwan_instructions = self.config.get("linwan_instructions", "知性温和，语气从容放松，落落大方，像日常发微信语音一样自然随性。")
        self.mumu_voice_id = self.config.get("mumu_voice_id", "voc_xy2p77mb2qs6")
        self.mumu_instructions = self.config.get("mumu_instructions", "轻快甜美，带一点点自然随性的笑意，像好朋友发语音聊天。")
        self.probability = float(self.config.get("default_probability", 0.4))
        
        self.voice_intent_keywords = [
            "发语音", "听声音", "发个语音", "说句话", "听听声音", "发段语音", "说来听听", "开口说话", "语音", "发一条语音"
        ]
        logger.info(f"[VoiceDirector] 专属音色导演插件 v1.2.0 已就绪（BreezeBlue专属克隆模式）！")

    async def _generate_breeze_audio(self, text: str, voice_id: str, instructions: str) -> str | None:
        if not self.breeze_api_key:
            logger.error("[VoiceDirector] 未配置 BreezeBlue API Key，跳过语音合成")
            return None

        url = f"https://api.breeze.blue/v1/text-to-speech/{voice_id}"
        headers = {
            "Authorization": f"Bearer {self.breeze_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "text": text,
            "instructions": instructions
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=25) as resp:
                    if resp.status == 200:
                        audio_bytes = await resp.read()
                        if audio_bytes:
                            temp_dir = Path("/AstrBot/data/temp")
                            temp_dir.mkdir(parents=True, exist_ok=True)
                            audio_file = temp_dir / f"breeze_{int(random.random()*1000000)}.mp3"
                            audio_file.write_bytes(audio_bytes)
                            return str(audio_file)
                    else:
                        err_text = await resp.text()
                        logger.error(f"[VoiceDirector] BreezeBlue TTS 失败 ({resp.status}): {err_text[:200]}")
        except Exception as e:
            logger.error(f"[VoiceDirector] BreezeBlue 合成异常: {e}")
        return None

    @filter.on_decorating_result()
    async def on_decorating_result(self, event: AstrMessageEvent):
        result = event.get_result()
        if not result or not result.chain:
            return

        plain_text = result.get_plain_text().strip()
        if not plain_text:
            return

        normalized = re.sub(r"[\[\]\s\-_]", "", plain_text).upper()
        if normalized in {"PASS", "SILENCE", "潜水", "IGNORE"}:
            logger.info("[VoiceDirector] 智能体静默决策，清空消息链")
            result.chain = []
            return

        user_msg = event.message_str or ""
        is_requested = any(w in user_msg for w in self.voice_intent_keywords)
        has_tags = any(t in plain_text for t in ["(", "（", "[", "【"])
        roll_hit = random.random() <= self.probability

        if not (is_requested or has_tags or roll_hit):
            return

        platform_name = event.get_platform_name()
        if "weixin" in platform_name:
            logger.debug("[VoiceDirector] 微信平台，保持纯文本发送，避免丢消息")
            return

        umo = event.unified_msg_origin.lower()
        if "mumu" in umo:
            voice_id = self.mumu_voice_id
            instructions = self.mumu_instructions
            role_desc = f"沐沐(Breeze克隆: {voice_id})"
        else:
            voice_id = self.linwan_voice_id
            instructions = self.linwan_instructions
            role_desc = f"林晚(Breeze克隆: {voice_id})"

        logger.info(f"[VoiceDirector] 触发专属克隆语音合成 -> {role_desc}: {plain_text[:30]}...")
        audio_path = await self._generate_breeze_audio(plain_text, voice_id, instructions)
        if not audio_path:
            logger.warning("[VoiceDirector] 音频生成失败，保留原始纯文本回复")
            return

        result.chain = [Record(file=audio_path, url=audio_path, text=plain_text)]
        logger.info(f"[VoiceDirector] 成功转换为纯语音消息: {audio_path}")
