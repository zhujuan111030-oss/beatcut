# 🎬 BeatCut — 自动卡点视频编辑器

上传一段视频 + 一首音乐，自动生成带卡点转场效果的短视频。

**适合一个人在 1-2 周内完成并上线的 AI 项目。**

## ✨ 功能

- 🎵 **自动节拍检测** — 使用 scipy+ffmpeg 分析音乐节拍和节奏
- ✂️ **智能卡点剪辑** — 视频片段自动对齐到每个节拍点
- 🎨 **4 种特效风格** — 平滑 / 动感 / 震感 / 电影感
- 📱 **多分辨率支持** — 竖屏(9:16) / 横屏(16:9) / 方形(1:1)
- 🌐 **Web 界面** — Streamlit 拖拽上传，一键生成
- 💻 **命令行工具** — 支持单文件和批量处理

## 📦 安装

```bash
# 1. 克隆项目
cd beatcut

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 安装 ffmpeg (macOS)
brew install ffmpeg

# 或者 Linux
sudo apt install ffmpeg
```

## 🚀 使用方式

### Web 界面 (推荐)

```bash
streamlit run app.py
```

浏览器打开后，上传视频和音乐，选择风格，一键生成。

### 命令行

```bash
# 单文件模式
python cli.py video.mp4 --music song.mp3 --preset energy

# 指定输出和参数
python cli.py video.mp4 -m song.mp3 -o my_video.mp4 -p heavy --max-duration 30

# 批量处理 (一首视频 + 多首音乐)
python cli.py video.mp4 --batch "music/*.mp3" --output-dir ./results

# 查看所有风格
python cli.py --list-presets
```

### Python API

```python
from beatcut.video_editor import create_beat_video

create_beat_video(
    video_path="my_video.mp4",
    audio_path="music.mp3",
    output_path="output.mp4",
    preset="energy",           # 特效风格
    output_resolution=(1080, 1920),  # 竖屏
    max_duration=60,           # 最长 60 秒
)
```

## 🎨 特效风格

| 风格 | 转场 | 节拍特效 | 适合场景 |
|------|------|----------|----------|
| `smooth` | 滑动 | 无 | 日常 vlog |
| `energy` | 滑动 | 闪白 | 运动、舞蹈 |
| `heavy` | 硬切 | 震动 | 电音、嘻哈 |
| `cinematic` | 硬切 | 缩放脉冲 | 旅行、风景 |

## 📁 项目结构

```
beatcut/
├── app.py                  # Streamlit Web 界面
├── cli.py                  # 命令行入口
├── requirements.txt        # Python 依赖
├── README.md
└── beatcut/
    ├── __init__.py
    ├── beat_detector.py    # 节拍检测 (scipy+ffmpeg)
    ├── video_editor.py     # 视频剪辑引擎 (moviepy)
    └── effects.py          # 转场特效
```

## 🔧 技术栈

- **节拍检测**: scipy+ffmpeg (onset detection + beat tracking)
- **视频处理**: moviepy + ffmpeg
- **Web 界面**: Streamlit
- **特效**: 自定义帧变换 (缩放、滑动、闪白、震动)

## 💡 后续可以做的优化

- [ ] 更多转场效果 (旋转、模糊、色彩偏移)
- [ ] AI 识别视频中的精彩片段 (人体检测、表情识别)
- [ ] 支持多段视频素材混合剪辑
- [ ] 导出竖屏带字幕模板
- [ ] 一键发布到抖音/小红书格式
- [ ] GPU 加速渲染
- [ ] 在线 SaaS 版本

## 📄 License

MIT
