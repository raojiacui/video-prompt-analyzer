"""
Video Prompt Analyzer - 视频镜头分析 & 提示词反推工具
支持上传视频或图片，使用 AI 分析画面内容并生成提示词
"""

import sys
import os
import base64
import json
from pathlib import Path
from typing import List, Optional

# 修复 Qt 平台插件路径问题
import PyQt5
qt_path = os.path.dirname(PyQt5.__file__)
plugins_path = os.path.join(qt_path, 'Qt5', 'plugins')
if os.path.exists(plugins_path):
    os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugins_path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QScrollArea, QFrame, QFileDialog,
    QProgressBar, QMessageBox, QTabWidget, QSplitter, QCheckBox,
    QSpinBox, QGroupBox, QGridLayout, QDialog, QLineEdit, QFormLayout
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage, QFont, QPalette, QColor
import requests
from PIL import Image
import cv2
import json


# ==================== 配置文件 ====================
CONFIG_FILE = "config.json"


def load_config():
    """加载配置文件"""
    default_config = {
        "api_key": "",
        "proxy_host": "",
        "proxy_port": ""
    }
    try:
        config_path = os.path.join(os.path.dirname(__file__), CONFIG_FILE)
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                print(f"[DEBUG] 配置已加载: {config_path}")
                return {**default_config, **loaded}
    except Exception as e:
        print(f"[DEBUG] 加载配置失败: {e}")
    return default_config


def save_config(config):
    """保存配置文件"""
    try:
        config_path = os.path.join(os.path.dirname(__file__), CONFIG_FILE)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"[DEBUG] 配置已保存到: {config_path}")
    except Exception as e:
        print(f"[ERROR] 保存配置失败: {e}")


# ==================== 配置 ====================
# 支持: 智谱AI / Google Gemini / OpenRouter API
DEFAULT_API_KEY = os.environ.get("ZHIPU_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "") or os.environ.get("OPENROUTER_API_KEY", "")

# API 配置
ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
ZHIPU_MODEL = "glm-4.6v"  # 智谱视觉模型

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"
GEMINI_MODEL = "gemini-2.0-flash-exp"

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "google/gemini-3-flash-preview"

# 默认使用智谱AI
API_BASE_URL = ZHIPU_API_URL
MODEL_NAME = ZHIPU_MODEL

# 全局 API Key
api_key = DEFAULT_API_KEY

# 从配置文件加载
config = load_config()
if config["api_key"]:
    api_key = config["api_key"]


def get_api_key():
    global api_key
    return api_key


def set_api_key(key: str):
    global api_key
    api_key = key


# 代理设置
proxy_host = None
proxy_port = None


def get_proxy():
    global proxy_host, proxy_port
    if proxy_host and proxy_port:
        return {"http": f"http://{proxy_host}:{proxy_port}", "https": f"http://{proxy_host}:{proxy_port}"}
    return None


def set_proxy(host: str, port: str):
    global proxy_host, proxy_port
    proxy_host = host if host else None
    proxy_port = port if port else None


# ==================== 设置对话框 ====================
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(450)
        self.setModal(True)

        layout = QFormLayout(self)

        # API Key
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setText(config.get("api_key", ""))
        self.api_key_input.setPlaceholderText("输入你的 API Key")
        layout.addRow("API Key:", self.api_key_input)

        # 代理设置
        proxy_layout = QHBoxLayout()
        self.proxy_host_input = QLineEdit()
        self.proxy_host_input.setPlaceholderText("127.0.0.1")
        self.proxy_host_input.setText(config.get("proxy_host", proxy_host or ""))
        self.proxy_port_input = QLineEdit()
        self.proxy_port_input.setPlaceholderText("7890")
        self.proxy_port_input.setText(config.get("proxy_port", str(proxy_port) if proxy_port else ""))
        proxy_layout.addWidget(QLabel("地址:"))
        proxy_layout.addWidget(self.proxy_host_input)
        proxy_layout.addWidget(QLabel("端口:"))
        proxy_layout.addWidget(self.proxy_port_input)
        layout.addRow("代理 (VPN需开启):", proxy_layout)

        help_label = QLabel(
            "\n【API 选项】\n\n"
            "1. 智谱AI (推荐，国内):\n"
            "   • 获取: https://open.bigmodel.cn/usercenter/apikeys\n"
            "   • Key 格式: 包含点号的密钥\n"
            "   • 模型: glm-4v (支持图片分析)\n"
            "   • 不需要代理\n\n"
            "2. Google Gemini (免费):\n"
            "   • 获取: https://aistudio.google.com/app/apikey\n"
            "   • Key 格式: AIza 开头\n"
            "   • 需要代理 (VPN)\n\n"
            "3. OpenRouter:\n"
            "   • 获取: https://openrouter.ai/keys\n"
            "   • Key 格式: sk-or-v1 开头\n"
            "   • 不需要代理"
        )
        help_label.setStyleSheet("color: #888;")
        layout.addRow(help_label)

        buttons = QHBoxLayout()
        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self.save_and_close)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)

        buttons.addStretch()
        buttons.addWidget(btn_cancel)
        buttons.addWidget(btn_save)
        layout.addRow(buttons)

    def save_and_close(self):
        key = self.api_key_input.text().strip()
        print(f"[DEBUG] 保存 API Key: {key[:10]}..." if key else "[DEBUG] API Key 为空")
        set_api_key(key)

        host = self.proxy_host_input.text().strip()
        port = self.proxy_port_input.text().strip()
        set_proxy(host, port)

        # 保存到配置文件
        config_data = {
            "api_key": key,
            "proxy_host": host,
            "proxy_port": port
        }
        save_config(config_data)

        # 立即验证是否保存成功
        try:
            config_path = os.path.join(os.path.dirname(__file__), CONFIG_FILE)
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    print(f"[DEBUG] 验证保存成功，api_key长度: {len(saved.get('api_key', ''))}")
            else:
                print(f"[ERROR] 配置文件不存在: {config_path}")
        except Exception as e:
            print(f"[ERROR] 验证失败: {e}")

        self.accept()


# ==================== 视频处理线程 ====================
class VideoProcessor(QThread):
    progress = pyqtSignal(int)
    frame_extracted = pyqtSignal(str, int, int)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, video_path: str, frame_count: int = 8):
        super().__init__()
        self.video_path = video_path
        self.frame_count = frame_count
        self.output_dir = Path("temp_frames")
        self.output_dir.mkdir(exist_ok=True)

    def run(self):
        try:
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                self.error.emit("无法打开视频文件")
                return

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = total_frames / fps if fps > 0 else 0

            frames = []
            interval = max(1, total_frames // self.frame_count)

            for i in range(self.frame_count):
                frame_idx = min(i * interval, total_frames - 1)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                if ret:
                    frame_path = str(self.output_dir / f"frame_{i:03d}.jpg")
                    cv2.imwrite(frame_path, frame)
                    frames.append(frame_path)
                    self.progress.emit(int((i + 1) / self.frame_count * 100))
                    self.frame_extracted.emit(frame_path, i, self.frame_count)

            cap.release()
            self.finished.emit(frames)
        except Exception as e:
            self.error.emit(f"视频处理出错: {str(e)}")


# ==================== AI 分析线程 ====================
class AIAnalyzer(QThread):
    progress = pyqtSignal(str)
    result = pyqtSignal(str, str)
    batch_complete = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, frames: List[str], analyze_mode: str = "single"):
        super().__init__()
        self.frames = frames
        self.analyze_mode = analyze_mode

        self.analysis_prompt = """# 视频镜头提示词反推专家

你是一位精通视觉语言和AI视频生成的提示词工程师。请对这张视频截图进行**专业级深度分析**，并输出可直接用于AI视频生成的结构化提示词。

---

## 📊 分析维度（请按以下顺序逐项分析）

### 一、画面主体 (Subject)
- **人物特征**：性别、年龄、外貌、表情、发型、妆容
- **人物动作**：姿态、手势、运动状态、朝向
- **服装配饰**：款式、颜色、材质、细节元素
- **其他主体**：动物/物体/图标等核心元素

### 二、环境场景 (Environment)
- **场景类型**：室内/室外/自然/城市/虚拟/抽象
- **具体场景**：街道/房间/森林/海滩/工作室等
- **时段天气**：清晨/正午/黄昏/深夜 + 晴/雨/雪/雾/风
- **背景元素**：建筑/植被/道具/招牌/装饰细节
- **空间深度**：前景/中景/背景的层次关系

### 三、镜头语言 (Camera)
- **拍摄角度**：平视/低角度仰拍/高角度俯拍/鸟瞰/虫眼/荷兰角
- **镜头景别**：极端远景(E LS)/远景(LS)/全景(FS)/中景(MS)/近景(MCU)/特写(CU)/大特写(ECU)
- **运镜方式**：固定/推镜头(Dolly In)/拉镜头(Dolly Out)/摇摄(Pan)/俯仰(Tilt)/跟随/环绕/手持晃动/滑动变焦
- **焦点控制**：合焦位置/景深浅深/焦点转移/背景虚化程度
- **构图法则**：三分法/黄金分割/引导线/框架构图/对称/居中/留白

### 四、光影照明 (Lighting)
- **光源类型**：自然光(日光/月光)/人造光(路灯/霓虹/室内灯/屏幕光)
- **光照方向**：顺光/侧光/逆光/顶光/底光
- **光比氛围**：柔和/强烈/高反差/低反差/剪影
- **特殊光效**：体积光/镜头光晕/反射光/辉光/阴影形状
- **色温色调**：暖调(金橙)/冷调(蓝青)/中性/赛博朋克霓虹

### 五、美术风格 (Style)
- **视觉风格**：写实/电影感/动漫/3D渲染/油画/水彩/复古胶片/赛博朋克/极简主义
- **色彩体系**：主色调/辅助色/点缀色 + 配色方案(互补/类比/单色)
- **饱和对比**：高饱和/低饱和/高对比/低对比/柔和/浓郁
- **质感材质**：光滑/粗糙/金属/织物/玻璃/液体/烟雾
- **后期处理**：胶片颗粒/色差/晕影/模糊/锐化/LUT滤镜

### 六、氛围情绪 (Mood)
- **情感基调**：宁静/紧张/温馨/孤独/浪漫/神秘/活力/忧郁/科幻感
- **叙事暗示**：故事背景/情节暗示/时间感/空间感
- **感官体验**：温度感/声音暗示/气味联想/触感
- **节奏动态**：静止/缓慢/快速/动荡

---

## 📝 输出格式（严格按此格式输出）

```
═══════════════════════════════════════════════════════════════
【画面深度描述】
(用一段150-200字的文字，整体描述画面，包含主要视觉元素和整体感受，语言生动但精准)

═══════════════════════════════════════════════════════════════
【AI视频生成提示词】

📌 核心提示词：
(一行精炼的提示词，可直接用于AI视频生成，包含最关键的元素)

───────────────────────────────────────────────────────────────

🎬 主体详细：
• 人物：...
• 动作：...
• 服装：...

🏞️ 场景环境：
• 场景类型：...
• 时段天气：...
• 空间层次：...

📷 镜头语言：
• 角度：[xx度] [具体角度]
• 景别：[具体景别]
• 运镜：[运镜方式] + [速度描述]
• 焦点：[焦点描述]
• 构图：[构图法则]

💡 光影照明：
• 光源：...
• 方向：...
• 光比：...
• 色温：...

🎨 美术风格：
• 视觉风格：[xx风格]
• 色彩：[主色调] + [配色方案]
• 质感：...
• 后期：...

✨ 氛围情绪：
• 基调：...
• 叙事：...
• 节奏：...

───────────────────────────────────────────────────────────────

🔧 技术参数建议：
• 宽高比：[如 16:9 / 9:16 / 21:9]
• 运动强度：[静止/微动/中/剧烈]
• 时长建议：[建议秒数]
• 负面提示词：(避免的元素，如模糊、变形等)
```

---

## ⚠️ 注意事项
1. 用词精准专业，避免模糊表述
2. 数值化描述优先（如"45度角"而非"斜角"）
3. 提示词优先级：主体 > 场景 > 镜头 > 光影 > 风格 > 氛围
4. 核心提示词要简洁有力，适合直接复制使用
5. 考虑AI视频生成的可实现性
"""

        self.batch_prompt = """# 视频镜头序列提示词反推专家

你是一位精通影视语言和AI视频生成的提示词工程师。这组截图来自**同一视频的不同帧**，请进行**序列级分析**。

---

## 📊 分析维度

### 一、时间连贯性 (Temporal Continuity)
- **帧间变化**：逐帧对比，识别主体、场景、光影的变化规律
- **运动轨迹**：分析人物/物体的运动路径和方向
- **时间流逝**：判断视频时间跨度（瞬间/数秒/更长）

### 二、镜头运动解析 (Camera Movement)
- **运镜类型**：推/拉/摇/仰/俯/跟随/环绕/手持
- **运动速度**：静止/缓慢/匀速/加速/减速/急速
- **运动轨迹**：直线/弧线/复杂路径
- **起止状态**：镜头起始位置和终止位置的关系

### 三、视觉一致性 (Visual Consistency)
- **风格统一**：色调、光影、质感的稳定性
- **变化点**：识别帧间的视觉突变（如切换场景/光线变化）
- **重复元素**：跨帧反复出现的视觉符号

### 四、叙事节奏 (Narrative Rhythm)
- **节奏类型**：静态/缓慢/中等/快速/动荡
- **情绪曲线**：情感基调的变化趋势
- **高潮点**：视觉冲击力最强的帧

---

## 📝 输出格式（严格按此格式输出）

```
═══════════════════════════════════════════════════════════════
【视频整体分析】

📖 叙事概述：
(150字以内，描述这个片段的整体内容和故事)

───────────────────────────────────────────────────────────────

🎬 镜头运动分析：
• 运镜方式：[具体运镜类型]
• 运动方向：[描述运动轨迹]
• 运动速度：[速度描述]
• 镜头跨度：从[起始状态]到[结束状态]

═══════════════════════════════════════════════════════════════
【视觉风格统一分析】

🎨 风格特征：
• 整体风格：[xx风格]
• 色彩体系：[主色调] + [贯穿帧的配色]
• 光影模式：[统一的光照特征]
• 质感特征：[共同的质感元素]

───────────────────────────────────────────────────────────────

📊 逐帧关键差异：
帧1：[最突出的视觉特征/变化点]
帧2：[相对于帧1的变化]
帧3：[相对于帧2的变化]
...（以此类推）

═══════════════════════════════════════════════════════════════
【AI视频复现提示词】

📌 核心提示词：
(一行精炼提示词，可直接用于AI视频生成，包含运镜、主体、场景的核心描述)

───────────────────────────────────────────────────────────────

🎬 运镜参数：
• 类型：[运镜类型]
• 速度：[速度描述]
• 方向：[运动方向]

👥 主体元素：
• 主要主体：[跨帧出现的主要元素]
• 动作变化：[动作的演变]

🏞️ 场景设定：
• 场景类型：...
• 持续元素：[贯穿始终的场景特征]

💡 光影风格：
• 统一光照：...
• 色调倾向：...

🎨 美术风格：
• 视觉风格：...
• 关键特征：[3-5个关键词]

✨ 氛围情绪：
• 基调：...
• 节奏：...

───────────────────────────────────────────────────────────────

🔧 技术参数建议：
• 宽高比：[如 16:9]
• 时长建议：[建议秒数，基于帧间变化推断]
• 运动强度：[静止/微动/中/剧烈]
• 负面提示词：(避免的元素)
```

---

## ⚠️ 注意事项
1. 重点关注**帧间变化**和**运镜规律**
2. 提示词要能复现出"动态感"而非静态画面
3. 核心提示词需包含运镜描述
4. 推断合理的视频时长
"""

    def encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    def call_api(self, messages: List[dict]) -> Optional[str]:
        api_key = get_api_key()

        # 判断 API 类型
        if "." in api_key and len(api_key) > 30:
            # 智谱AI API Key 格式: id.secret
            return self.call_zhipu_api(messages, api_key)
        elif api_key.startswith("AIza") or api_key.startswith("GOOA"):
            # Google Gemini API
            return self.call_gemini_api(messages, api_key)
        else:
            # OpenRouter API
            return self.call_openrouter_api(messages, api_key)

    def call_zhipu_api(self, messages: List[dict], api_key: str) -> Optional[str]:
        """调用智谱AI API"""
        proxies = get_proxy()

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # 转换消息格式为智谱AI格式
        zhipu_messages = []
        for msg in messages:
            if msg["role"] == "user":
                content_list = []
                for item in msg["content"]:
                    if item["type"] == "text":
                        content_list.append({"type": "text", "text": item["text"]})
                    elif item["type"] == "image_url":
                        url = item["image_url"]["url"]
                        # 智谱AI格式
                        content_list.append({
                            "type": "image_url",
                            "image_url": {"url": url}
                        })
                zhipu_messages.append({"role": "user", "content": content_list})

        payload = {
            "model": ZHIPU_MODEL,
            "messages": zhipu_messages,
            "max_tokens": 4096,
            "temperature": 0.7,
        }

        # 调试输出
        print(f"[DEBUG] 智谱AI请求: {json.dumps(payload, ensure_ascii=False)[:500]}...")

        try:
            response = requests.post(ZHIPU_API_URL, headers=headers, json=payload, timeout=120, proxies=proxies)
            print(f"[DEBUG] 响应状态: {response.status_code}")
            print(f"[DEBUG] 响应内容: {response.text[:500]}...")
            response.raise_for_status()
            result = response.json()

            if "choices" not in result or len(result["choices"]) == 0:
                self.error.emit(f"智谱AI 返回空结果: {result}")
                return None

            return result["choices"][0]["message"]["content"]
        except requests.HTTPError as e:
            error_detail = str(e)
            try:
                error_json = response.json()
                error_detail = error_json.get("error", {}).get("message", str(error_json))
            except:
                pass
            self.error.emit(f"智谱AI 错误: {error_detail}")
            return None
        except Exception as e:
            self.error.emit(f"请求失败: {str(e)}")
            return None

    def call_gemini_api(self, messages: List[dict], api_key: str) -> Optional[str]:
        """调用 Google Gemini API"""
        # 使用代理（如果设置了）
        proxies = get_proxy()

        # 提取图片和文本
        text_content = ""
        images = []

        for msg in messages:
            if msg["role"] == "user":
                for content in msg["content"]:
                    if content["type"] == "text":
                        text_content += content["text"]
                    elif content["type"] == "image_url":
                        url = content["image_url"]["url"]
                        if url.startswith("data:image/jpeg;base64,"):
                            images.append(url.split(",")[1])

        # 构建 Gemini 请求格式
        contents = []
        for img in images:
            contents.append({
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": "image/jpeg", "data": img}},
                    {"text": text_content}
                ]
            })

        payload = {"contents": contents, "generationConfig": {"maxOutputTokens": 4096}}

        try:
            url = f"{GEMINI_API_URL}?key={api_key}"
            response = requests.post(url, json=payload, timeout=120, proxies=proxies)
            response.raise_for_status()
            result = response.json()

            if "candidates" not in result or len(result["candidates"]) == 0:
                self.error.emit(f"API 返回空结果: {result}")
                return None

            return result["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            self.error.emit(f"Gemini API 错误: {str(e)}\n\n请确保:\n1. VPN/代理已开启\n2. 代理设置正确")
            return None

    def call_openrouter_api(self, messages: List[dict], api_key: str) -> Optional[str]:
        """调用 OpenRouter API"""
        # 使用代理（如果设置了）
        proxies = get_proxy()

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com",
            "X-Title": "Video Prompt Analyzer",
        }

        # OpenRouter 使用自己的 URL 和模型名称
        payload = {
            "model": OPENROUTER_MODEL,
            "messages": messages,
            "max_tokens": 4096,
        }

        try:
            response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=120, proxies=proxies)
            response.raise_for_status()
            result = response.json()

            if "choices" not in result or len(result["choices"]) == 0:
                self.error.emit(f"API 返回空结果: {result}")
                return None

            return result["choices"][0]["message"]["content"]
        except requests.HTTPError as e:
            error_detail = str(e)
            try:
                error_json = response.json()
                error_detail = error_json.get("error", {}).get("message", error_json)
            except:
                pass
            self.error.emit(f"OpenRouter API 错误: {error_detail}")
            return None
        except Exception as e:
            self.error.emit(f"请求失败: {str(e)}")
            return None

    def run(self):
        print(f"[DEBUG] AIAnalyzer run() called, frames: {len(self.frames)}, mode: {self.analyze_mode}")

        if not get_api_key():
            self.error.emit("请先点击「⚙️ API 设置」按钮填写 API Key\n\n推荐使用智谱AI（国内，无需代理）:\n访问 https://open.bigmodel.cn/usercenter/apikeys 获取")
            return

        print(f"[DEBUG] API Key found: {get_api_key()[:20]}...")
        self.progress.emit("开始分析...")
        try:
            if self.analyze_mode == "all_together" and len(self.frames) > 1:
                print(f"[DEBUG] Calling analyze_batch...")
                self.analyze_batch()
            elif self.analyze_mode == "batch":
                print(f"[DEBUG] Calling analyze_batch...")
                self.analyze_batch()
            else:
                print(f"[DEBUG] Calling analyze_single...")
                self.analyze_single()
        except Exception as e:
            print(f"[DEBUG] Error in run(): {e}")
            import traceback
            traceback.print_exc()
            self.error.emit(f"分析出错: {str(e)}")

        if self.analyze_mode == "all_together" and len(self.frames) > 1:
            self.analyze_batch()
        elif self.analyze_mode == "batch":
            self.analyze_batch()
        else:
            self.analyze_single()

    def analyze_single(self):
        results = {}
        for i, frame in enumerate(self.frames):
            self.progress.emit(f"正在分析第 {i+1}/{len(self.frames)} 帧...")

            image_base64 = self.encode_image(frame)
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.analysis_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                    ]
                }
            ]

            response = self.call_api(messages)
            if response:
                results[frame] = response
                self.result.emit(frame, response)

        if results:
            self.batch_complete.emit(results)

    def analyze_batch(self):
        self.progress.emit("正在批量分析所有帧...")

        content = [{"type": "text", "text": self.batch_prompt}]
        for frame in self.frames:
            image_base64 = self.encode_image(frame)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
            })

        messages = [{"role": "user", "content": content}]

        response = self.call_api(messages)
        if response:
            results = {frame: response for frame in self.frames}
            self.batch_complete.emit(results)


# ==================== 主窗口 ====================
class VideoPromptAnalyzer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_frames = []
        self.prompts = {}
        self.current_media_path = None

        self.init_ui()
        self.apply_dark_theme()

    def init_ui(self):
        self.setWindowTitle("Video Prompt Analyzer v2.0 - 大字体版")
        self.setMinimumSize(1400, 900)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        toolbar = self.create_toolbar()
        main_layout.addWidget(toolbar)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, 1)

        left_panel = self.create_preview_panel()
        splitter.addWidget(left_panel)

        right_panel = self.create_result_panel()
        splitter.addWidget(right_panel)

        splitter.setSizes([700, 700])

        self.statusBar().showMessage("就绪")

    def create_toolbar(self) -> QFrame:
        toolbar = QFrame()
        toolbar.setFrameStyle(QFrame.Shape.StyledPanel)
        toolbar.setMaximumHeight(120)

        layout = QGridLayout(toolbar)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(10)

        btn_video = QPushButton("📹 加载视频")
        btn_video.setMinimumHeight(50)
        btn_video.setFont(QFont("Microsoft YaHei", 24, QFont.Weight.Bold))
        btn_video.clicked.connect(self.load_video)
        layout.addWidget(btn_video, 0, 0)

        btn_images = QPushButton("🖼️ 加载图片")
        btn_images.setMinimumHeight(50)
        btn_images.setFont(QFont("Microsoft YaHei", 24, QFont.Weight.Bold))
        btn_images.clicked.connect(self.load_images)
        layout.addWidget(btn_images, 0, 1)

        btn_settings = QPushButton("⚙️ API 设置")
        btn_settings.setMinimumHeight(50)
        btn_settings.setFont(QFont("Microsoft YaHei", 24, QFont.Weight.Bold))
        btn_settings.clicked.connect(self.open_settings)
        layout.addWidget(btn_settings, 0, 2)

        settings_group = QGroupBox("视频帧设置")
        settings_group.setFont(QFont("Microsoft YaHei", 24))
        settings_layout = QHBoxLayout(settings_group)

        label_frames = QLabel("提取帧数:")
        label_frames.setFont(QFont("Microsoft YaHei", 24))
        settings_layout.addWidget(label_frames)
        self.frame_spin = QSpinBox()
        self.frame_spin.setRange(1, 30)
        self.frame_spin.setValue(8)
        self.frame_spin.setFont(QFont("Microsoft YaHei", 24))
        settings_layout.addWidget(self.frame_spin)

        layout.addWidget(settings_group, 0, 3)

        mode_group = QGroupBox("分析模式")
        mode_group.setFont(QFont("Microsoft YaHei", 24))
        mode_layout = QHBoxLayout(mode_group)

        self.mode_single = QCheckBox("逐帧分析")
        self.mode_single.setFont(QFont("Microsoft YaHei", 24))
        self.mode_single.setChecked(True)
        self.mode_single.toggled.connect(self.on_mode_change)
        mode_layout.addWidget(self.mode_single)

        self.mode_batch = QCheckBox("批量对比")
        self.mode_batch.setFont(QFont("Microsoft YaHei", 24))
        mode_layout.addWidget(self.mode_batch)

        layout.addWidget(mode_group, 0, 4)

        btn_analyze = QPushButton("🔍 开始分析")
        btn_analyze.setMinimumHeight(60)
        btn_analyze.setMinimumWidth(180)
        btn_analyze.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 28px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #555;
            }
        """)
        btn_analyze.clicked.connect(self.start_analysis)
        layout.addWidget(btn_analyze, 0, 5, 2, 1)

        btn_export = QPushButton("💾 导出结果")
        btn_export.setMinimumHeight(50)
        btn_export.setFont(QFont("Microsoft YaHei", 24, QFont.Weight.Bold))
        btn_export.clicked.connect(self.export_results)
        layout.addWidget(btn_export, 1, 0)

        btn_clear = QPushButton("🗑️ 清空")
        btn_clear.setMinimumHeight(50)
        btn_clear.setFont(QFont("Microsoft YaHei", 24, QFont.Weight.Bold))
        btn_clear.clicked.connect(self.clear_all)
        layout.addWidget(btn_clear, 1, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar, 1, 2, 1, 2)

        return toolbar

    def create_preview_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)

        title = QLabel("📷 画面预览")
        title.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(400, 300)
        self.preview_label.setStyleSheet("background-color: #2a2a2a; border-radius: 8px;")
        self.preview_label.setFont(QFont("Microsoft YaHei", 14))
        self.preview_label.setText("请加载视频或图片\n\n支持格式:\n• 视频: MP4, MOV, AVI\n• 图片: JPG, PNG")
        layout.addWidget(self.preview_label, 1)

        thumb_label = QLabel("帧序列:")
        thumb_label.setFont(QFont("Microsoft YaHei", 14))
        layout.addWidget(thumb_label)

        self.thumbnail_area = QScrollArea()
        self.thumbnail_area.setMaximumHeight(120)
        self.thumbnail_area.setWidgetResizable(True)
        self.thumbnail_widget = QWidget()
        self.thumbnail_layout = QHBoxLayout(self.thumbnail_widget)
        self.thumbnail_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.thumbnail_area.setWidget(self.thumbnail_widget)
        layout.addWidget(self.thumbnail_area)

        return panel

    def create_result_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)

        title = QLabel("📝 分析结果 & 提示词")
        title.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.tab_widget = QTabWidget()
        self.tab_widget.setFont(QFont("Microsoft YaHei", 14))
        layout.addWidget(self.tab_widget, 1)

        return panel

    def on_mode_change(self):
        if self.sender() == self.mode_single and self.mode_single.isChecked():
            self.mode_batch.setChecked(False)
        elif self.sender() == self.mode_batch and self.mode_batch.isChecked():
            self.mode_single.setChecked(False)

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QFrame {
                background-color: #2a2a2a;
                border-radius: 8px;
            }
            QPushButton {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #4a4a4a;
                border-radius: 6px;
                padding: 10px 18px;
                font-size: 28px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #5a5a5a;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666;
            }
            QTextEdit {
                background-color: #1a1a1a;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 15px;
                font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
                font-size: 28px;
                line-height: 1.6;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QTabWidget::pane {
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2a2a2a;
                color: #aaa;
                padding: 12px 25px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
                font-size: 24px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                color: #4CAF50;
            }
            QTabBar::tab:hover {
                background-color: #252525;
            }
            QGroupBox {
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                margin-top: 10px;
                padding: 12px;
                font-size: 24px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
            }
            QSpinBox {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 6px;
                font-size: 24px;
                min-height: 25px;
            }
            QProgressBar {
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                text-align: center;
                background-color: #2a2a2a;
                font-size: 24px;
                min-height: 25px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 24px;
            }
            QLineEdit {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 8px;
                font-size: 24px;
                min-height: 30px;
            }
            QFileDialog {
                font-size: 24px;
            }
        """)

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            key = get_api_key()
            if key:
                self.statusBar().showMessage("API Key 已保存 ✓")
            else:
                self.statusBar().showMessage("⚠️ 未设置 API Key，将无法使用分析功能")

    def load_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择视频文件",
            "",
            "视频文件 (*.mp4 *.mov *.avi *.mkv *.webm);;所有文件 (*.*)"
        )
        if file_path:
            self.current_media_path = file_path
            self.process_video(file_path)

    def load_images(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择图片文件",
            "",
            "图片文件 (*.jpg *.jpeg *.png *.webp);;所有文件 (*.*)"
        )
        if file_paths:
            self.current_media_path = file_paths
            self.display_images(file_paths)

    def process_video(self, video_path: str):
        self.statusBar().showMessage(f"加载视频: {Path(video_path).name}")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        frame_count = self.frame_spin.value()
        self.video_processor = VideoProcessor(video_path, frame_count)
        self.video_processor.progress.connect(self.progress_bar.setValue)
        self.video_processor.frame_extracted.connect(self.on_frame_extracted)
        self.video_processor.finished.connect(self.on_frames_ready)
        self.video_processor.error.connect(self.on_video_error)
        self.video_processor.start()

    def on_video_error(self, error_msg: str):
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "视频加载失败", error_msg)

    def on_frame_extracted(self, frame_path: str, index: int, total: int):
        try:
            if index == 0:
                self.display_image(frame_path)

            thumb_btn = QPushButton()
            thumb_btn.setFixedSize(80, 60)
            thumb_btn.setFlat(True)

            pixmap = QPixmap(frame_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(80, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                thumb_btn.setIcon(scaled_pixmap)
                thumb_btn.setIconSize(scaled_pixmap.size())

            thumb_btn.clicked.connect(lambda checked, fp=frame_path: self.display_image(fp))
            thumb_btn.setToolTip(f"帧 {index + 1}")

            self.thumbnail_layout.addWidget(thumb_btn)
        except Exception as e:
            print(f"Error displaying frame: {e}")

    def on_frames_ready(self, frames: List[str]):
        self.current_frames = frames
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage(f"已提取 {len(frames)} 帧")

    def display_images(self, file_paths: List[str]):
        self.current_frames = file_paths
        self.display_image(file_paths[0])

        for i, path in enumerate(file_paths):
            thumb_btn = QPushButton()
            thumb_btn.setFixedSize(80, 60)
            thumb_btn.setFlat(True)

            pixmap = QPixmap(path)
            scaled_pixmap = pixmap.scaled(80, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            thumb_btn.setIcon(scaled_pixmap)
            thumb_btn.setIconSize(scaled_pixmap.size())
            thumb_btn.clicked.connect(lambda: self.display_image(path))
            thumb_btn.setToolTip(f"图片 {i + 1}")

            self.thumbnail_layout.addWidget(thumb_btn)

        self.statusBar().showMessage(f"已加载 {len(file_paths)} 张图片")

    def display_image(self, image_path: str):
        try:
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                self.preview_label.setText(f"无法加载图片: {Path(image_path).name}")
                return

            label_size = self.preview_label.size()
            if label_size.width() < 10 or label_size.height() < 10:
                label_size = self.preview_label.minimumSize()

            scaled = pixmap.scaled(
                label_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.preview_label.setPixmap(scaled)
            self.current_preview_path = image_path
        except Exception as e:
            self.preview_label.setText(f"加载失败: {str(e)}")

    def start_analysis(self):
        print(f"[DEBUG] start_analysis called, current_frames: {len(self.current_frames)}")

        if not self.current_frames:
            QMessageBox.warning(self, "提示", "请先加载视频或图片")
            return

        print(f"[DEBUG] Frames: {self.current_frames}")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        if self.mode_batch.isChecked():
            mode = "batch" if len(self.current_frames) > 1 else "single"
        else:
            mode = "all_together" if len(self.current_frames) > 1 else "single"

        print(f"[DEBUG] Mode: {mode}")
        self.analyzer = AIAnalyzer(self.current_frames, mode)
        self.analyzer.progress.connect(self.statusBar().showMessage)
        self.analyzer.result.connect(self.on_analysis_result)
        self.analyzer.batch_complete.connect(self.on_batch_complete)
        self.analyzer.error.connect(self.on_analysis_error)

        print(f"[DEBUG] Starting analyzer thread...")
        self.analyzer.start()

    def on_analysis_result(self, frame_path: str, result: str):
        self.prompts[frame_path] = result

        frame_name = Path(frame_path).stem
        tab_name = f"帧 {self.current_frames.index(frame_path) + 1}"

        existing_tabs = [self.tab_widget.tabText(i) for i in range(self.tab_widget.count())]
        if tab_name in existing_tabs:
            idx = existing_tabs.index(tab_name)
            widget = self.tab_widget.widget(idx)
            text_edit = widget.findChild(QTextEdit)
            if text_edit:
                text_edit.setPlainText(result)
        else:
            text_edit = QTextEdit()
            text_edit.setFont(QFont("Microsoft YaHei", 28))
            text_edit.setPlainText(result)
            self.tab_widget.addTab(text_edit, tab_name)

        self.progress_bar.setValue(int(len(self.prompts) / len(self.current_frames) * 100))

    def on_batch_complete(self, results: dict):
        self.prompts = results
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("分析完成!")

        self.tab_widget.clear()

        if len(results) == 1:
            text_edit = QTextEdit()
            text_edit.setFont(QFont("Microsoft YaHei", 28))
            text_edit.setPlainText(list(results.values())[0])
            self.tab_widget.addTab(text_edit, "分析结果")
        else:
            if self.mode_batch.isChecked():
                text_edit = QTextEdit()
                text_edit.setFont(QFont("Microsoft YaHei", 28))
                text_edit.setPlainText(list(results.values())[0])
                self.tab_widget.addTab(text_edit, "统一分析")
            else:
                for frame_path, result in results.items():
                    frame_name = Path(frame_path).stem
                    idx = self.current_frames.index(frame_path)
                    text_edit = QTextEdit()
                    text_edit.setFont(QFont("Microsoft YaHei", 28))
                    text_edit.setPlainText(result)
                    self.tab_widget.addTab(text_edit, f"帧 {idx + 1}")

    def on_analysis_error(self, error_msg: str):
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "分析失败", error_msg)

    def export_results(self):
        if not self.prompts:
            QMessageBox.warning(self, "提示", "没有可导出的结果")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存分析结果",
            "video_prompts.txt",
            "文本文件 (*.txt);;Markdown文件 (*.md);;JSON文件 (*.json)"
        )

        if not file_path:
            return

        try:
            if file_path.endswith('.json'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.prompts, f, ensure_ascii=False, indent=2)
            elif file_path.endswith('.md'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("# 视频镜头分析结果\n\n")
                    for frame_path, prompt in self.prompts.items():
                        f.write(f"## {Path(frame_path).name}\n\n```\n{prompt}\n```\n\n")
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    for frame_path, prompt in self.prompts.items():
                        f.write(f"{'='*50}\n")
                        f.write(f"文件: {Path(frame_path).name}\n")
                        f.write(f"{'='*50}\n\n")
                        f.write(f"{prompt}\n\n")

            QMessageBox.information(self, "成功", f"结果已保存到:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"保存文件时出错:\n{str(e)}")

    def clear_all(self):
        self.current_frames = []
        self.prompts = {}
        self.preview_label.clear()
        self.preview_label.setText("请加载视频或图片")
        self.tab_widget.clear()

        while self.thumbnail_layout.count():
            item = self.thumbnail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        import shutil
        temp_dir = Path("temp_frames")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            temp_dir.mkdir()

        self.statusBar().showMessage("已清空")


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = VideoPromptAnalyzer()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
