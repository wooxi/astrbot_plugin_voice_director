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

@register("voice_director", "wooxi", "多角色自适应专属音色分发与智能语音导演插件", "v1.1.0")
class VoiceDirectorPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.context = context
        self.config = config or {}
        
        self.api_key = self.config.get("api_key", "").strip()
        self.api_base = self.config.get("api_base", "https://api.xiaomimimo.com/v1").rstrip("/")
        
        # 自动回退读取 AstrBot 全局配置的小米密钥
        if not self.api_key:
            try:
                for p in self.context.astrbot_config.get("provider", []):
                    if "mimo" in p.get("id", "") or "xiaomi" in p.get("provider", ""):
                        if key := p.get("api_key"):
                            self.api_key = key
                            break
            except Exception:
                pass

        # 官方精品底座音色与微调指令
        self.linwan_voice = self.config.get("linwan_voice", "冰糖")
        self.linwan_style = self.config.get("linwan_style", "温和自然，生活化口语断句，平视舒适，落落大方，绝无广播腔和客服腔。")
        self.mumu_voice = self.config.get("mumu_voice", "茉莉")
        self.mumu_style = self.config.get("mumu_style", "轻柔温润，中高频通透，清甜自然，平易近人，绝无做作卖萌。")
        self.probability = float(self.config.get("default_probability", 0.4))
        
        self.voice_intent_keywords = [
            "发语音", "听声音", "发个语音", "说句话", "听听声音", "发段语音", "说来听听", "开口说话", "语音", "发一条语音"
        ]
        logger.info("[VoiceDirector] 专属音色导演插件已初始化就绪（官方精品音色底座模式）！")

    async def _generate_mimo_audio(self, text: str, voice_name: str, style_prompt: str) -> str | None:
        """调用小米官方精品音色 API，字字清晰，绝无吞音"""
        if not self.api_key:
            logger.error("[VoiceDirector] 未配置小米 API Key，跳过语音合成")
            return None

        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "mimo-v2.5-tts",
            "messages": [
                {"role": "user", "content": style_prompt},
                {"role": "assistant", "content": text}
            ],
            "audio": {
                "voice": voice_name,
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

        # 1. 检查静默暗号
        normalized = re.sub(r"[\[\]\s\-_]", "", plain_text).upper()
        if normalized in {"PASS", "SILENCE", "潜水", "IGNORE"}:
            logger.info("[VoiceDirector] 智能体静默决策，清空消息链")
            result.chain = []
            return

        # 2. 判断是否应该触发语音
        user_msg = event.message_str or ""
        is_requested = any(w in user_msg for w in self.voice_intent_keywords)
        has_tags = any(t in plain_text for t in ["(", "（", "[", "【"])
        roll_hit = random.random() <= self.probability

        if not (is_requested or has_tags or roll_hit):
            return

        # 3. 平台差异化处理 (微信端保持纯文本，防丢消息)
        platform_name = event.get_platform_name()
        if "weixin" in platform_name:
            logger.debug("[VoiceDirector] 微信平台，保持纯文本发送，避免丢消息")
            return

        # 4. 识别角色并选择专属官方精品音色与微调指令
        umo = event.unified_msg_origin.lower()
        if "mumu" in umo:
            voice_name = self.mumu_voice
            style_prompt = self.mumu_style
            role_desc = f"沐沐(底座: {voice_name})"
        else:
            voice_name = self.linwan_voice
            style_prompt = self.linwan_style
            role_desc = f"林晚(底座: {voice_name})"

        logger.info(f"[VoiceDirector] 触发精品语音合成 -> {role_desc}: {plain_text[:30]}...")
        audio_path = await self._generate_mimo_audio(plain_text, voice_name, style_prompt)
        if not audio_path:
            logger.warning("[VoiceDirector] 音频生成失败，保留原始纯文本回复")
            return

        # 5. 替换为纯语音条（飞书客户端完美支持纯语音条）
        result.chain = [Record(file=audio_path, url=audio_path, text=plain_text)]
        logger.info(f"[VoiceDirector] 成功转换为纯语音消息: {audio_path}")
