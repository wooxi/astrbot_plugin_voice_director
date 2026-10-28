import os
import re
import json
import random
import base64
import aiohttp
from pathlib import Path
from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.message_components import Plain, Record, Image, At, Json
from astrbot.api import logger
from astrbot.api.star import Context, Star, register

@register("voice_director", "wooxi", "多角色自适应专属音色分发与智能语音导演插件", "v1.0.0")
class VoiceDirectorPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.context = context
        self.config = config or {}
        
        self.api_key = self.config.get("api_key", "").strip()
        self.api_base = self.config.get("api_base", "https://api.xiaomimimo.com/v1").rstrip("/")
        
        # 如果未单独配置 API Key，自动从 AstrBot 全局配置中回退读取
        if not self.api_key:
            try:
                for p in self.context.astrbot_config.get("provider", []):
                    if "mimo" in p.get("id", "") or "xiaomi" in p.get("provider", ""):
                        if key := p.get("api_key"):
                            self.api_key = key
                            break
            except Exception:
                pass

        self.linwan_dir = self.config.get("linwan_director", "24岁普通年轻女性，音色清爽干净，音调自然平稳，完全没有撒娇、卖萌、娇嗲或做作感。发音自然放松，语调平实真诚，就像生活中普通朋友在咖啡厅对面坐着随口闲聊，真实朴素。")
        self.mumu_dir = self.config.get("mumu_director", "23-24岁年轻女性，音色清亮柔和、温润细腻，中高频通透，带有自然的柔甜质感。语速轻柔平稳，咬字大方舒适，带着一种发自内心的体贴与关照，真诚平视，绝不做作，令人感到彻底放松和心安。")
        self.probability = float(self.config.get("default_probability", 0.4))
        
        self.voice_intent_keywords = [
            "发语音", "听声音", "发个语音", "说句话", "听听声音", "发段语音", "说来听听", "开口说话", "语音", "发一条语音"
        ]
        logger.info("[VoiceDirector] 专属音色导演插件已初始化就绪！")

    async def _generate_mimo_audio(self, text: str, director: str) -> str | None:
        if not self.api_key:
            logger.error("[VoiceDirector] 未配置小米 API Key，跳过语音合成")
            return None

        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "mimo-v2.5-tts-voicedesign",
            "messages": [
                {"role": "user", "content": director},
                {"role": "assistant", "content": text}
            ],
            "audio": {
                "format": "wav"
            }
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=25) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        choices = data.get("choices", [])
                        if choices:
                            audio_b64 = choices[0].get("message", {}).get("audio", {}).get("data")
                            if audio_b64:
                                temp_dir = Path("/AstrBot/data/temp")
                                temp_dir.mkdir(parents=True, exist_ok=True)
                                audio_file = temp_dir / f"vd_{int(random.random()*1000000)}.wav"
                                audio_file.write_bytes(base64.b64decode(audio_b64))
                                return str(audio_file)
                    else:
                        err_text = await resp.text()
                        logger.error(f"[VoiceDirector] 小米 TTS 失败 ({resp.status}): {err_text[:200]}")
        except Exception as e:
            logger.error(f"[VoiceDirector] 生成音频异常: {e}")
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
            director = self.mumu_dir
            role_name = "沐沐(音色 B-2)"
        else:
            director = self.linwan_dir
            role_name = "林晚(音色 A)"

        logger.info(f"[VoiceDirector] 触发专属语音合成 -> {role_name}: {plain_text[:30]}...")
        audio_path = await self._generate_mimo_audio(plain_text, director)
        if not audio_path:
            logger.warning("[VoiceDirector] 音频生成失败，保留原始纯文本回复")
            return

        result.chain = [Record(file=audio_path, url=audio_path, text=plain_text)]
        logger.info(f"[VoiceDirector] 成功转换为纯语音消息: {audio_path}")