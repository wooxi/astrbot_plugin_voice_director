# astrbot_plugin_voice_director

> 🎙️ 专为 **AstrBot** 设计的**多角色自适应音色分发与智能语音导演插件**。现已全面支持 **BreezeBlue（微风蓝科技）** 官方 API 与自定义克隆音色（Voice ID），让每个数字人拥有独一无二、栩栩如生的真人体感嗓音！

---

## ✨ 核心特性 (v1.2.0)

1. **🎭 原生支持 BreezeBlue 声音克隆（Voice Cloning）**：
   - 直接支持绑定你在 BreezeBlue 控制台克隆的专属 `Voice ID`；
   - 自动识别当前会话角色（林晚 / 沐沐），动态调用对应的克隆音色；
   - 支持通过 `instructions` 参数以自然语言实时导演语气、情绪与语速。
2. **🎯 智能意图 100% 强触发**：
   - 当用户在聊天中表达*“发语音”、“听声音”、“说句话”*等明确意图，或智能体回复中带有情绪标签时，**100% 必定生成真实语音条**。
   - 日常闲聊则按可调概率自然触发，真实不造作。
3. **📱 多端平滑自适应**：
   - **飞书端**：只下发干净的原生纯语音条，不带多余的重复文字；
   - **微信端**：针对微信对话平台不支持原生音频条的特性，自动降级为纯文本，确保消息 100% 准确到达不被丢弃。
4. **🔒 智能心智静默兼容**：
   - 兼容大模型自主选择潜水/静默机制，当智能体决定不回复时自动清空消息链，不产生空包。

---

## 🛠️ 配置说明

| 配置项 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `engine` | string | `breezeblue` | 语音合成引擎（`breezeblue` / `mimo`） |
| `breeze_api_key` | string | `""` | BreezeBlue API Key (`brz_...`) |
| `linwan_voice_id` | string | `voc_yu7t5b4tx7c7` | 林晚专属克隆 Voice ID |
| `linwan_instructions` | text | *见配置* | 林晚语气导演指令 |
| `mumu_voice_id` | string | `voc_xy2p77mb2qs6` | 沐沐专属克隆 Voice ID |
| `mumu_instructions` | text | *见配置* | 沐沐语气导演指令 |
| `default_probability` | float | `0.4` | 日常闲聊语音触发概率 (0.0~1.0) |

---

## 📄 开源许可

本项目遵循 [MIT](LICENSE) 协议开源。
