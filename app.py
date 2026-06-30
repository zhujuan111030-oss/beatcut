"""Streamlit web app for BeatCut - beat-synced video editor.

Run with:
    streamlit run app.py
"""

import os
import tempfile
from pathlib import Path

import streamlit as st

from beatcut.video_editor import create_beat_video
from beatcut.effects import EFFECT_PRESETS

st.set_page_config(
    page_title="BeatCut - 卡点视频编辑器",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 BeatCut")
st.caption("上传视频 + 音乐，自动生成卡点效果短片")

# ---- Sidebar: Settings ----
with st.sidebar:
    st.header("⚙️ 设置")

    preset = st.selectbox(
        "特效风格",
        options=list(EFFECT_PRESETS.keys()),
        format_func=lambda x: f"{x} — {EFFECT_PRESETS[x]['description']}",
        index=1,
    )

    orientation = st.radio(
        "视频方向",
        options=["竖屏 (9:16)", "横屏 (16:9)", "方形 (1:1)"],
        index=0,
    )

    resolution_map = {
        "竖屏 (9:16)": (1080, 1920),
        "横屏 (16:9)": (1920, 1080),
        "方形 (1:1)": (1080, 1080),
    }
    output_resolution = resolution_map[orientation]

    fps = st.slider("输出帧率", 24, 60, 30)
    max_duration = st.slider("最大时长 (秒)", 15, 120, 60)
    keep_audio = st.checkbox("保留视频原声 (作为背景)", value=False)
    trim_to_video = st.checkbox("按视频长度裁剪音乐", value=True, help="开启后音乐会自动裁剪到视频时长")

    st.divider()
    st.caption("📦 输出格式: MP4 (H.264)")

# ---- Main: Upload ----
col1, col2 = st.columns(2)

with col1:
    st.subheader("📹 上传视频")
    video_files = st.file_uploader(
        "选择视频文件（支持多选）",
        type=["mp4", "mov", "avi", "mkv", "webm"],
        accept_multiple_files=True,
        key="video",
    )
    if video_files:
        st.caption(f"已选择 {len(video_files)} 个视频")
        for vf in video_files:
            with st.expander(f"🎬 {vf.name}", expanded=(len(video_files) == 1)):
                st.video(vf)

with col2:
    st.subheader("🎵 选择音乐")

    music_dir = os.path.join(os.path.dirname(__file__), "music")
    music_files = []
    if os.path.isdir(music_dir):
        music_files = sorted([
            f for f in os.listdir(music_dir)
            if f.lower().endswith(('.wav', '.mp3', '.m4a', '.ogg'))
        ])

    use_library = False
    selected_music = None

    if music_files:
        st.caption(f"📀 内置音乐库（{len(music_files)} 首）")
        selected_music = st.selectbox(
            "从音乐库选择",
            options=["（不使用音乐库）"] + music_files,
            key="music_library",
        )
        if selected_music and selected_music != "（不使用音乐库）":
            use_library = True
            lib_path = os.path.join(music_dir, selected_music)
            st.audio(lib_path)

    if not use_library:
        audio_file = st.file_uploader(
            "或上传音乐文件（不选则用视频原声）",
            type=["mp3", "wav", "m4a", "ogg", "flac"],
            key="audio",
        )
        if audio_file:
            st.audio(audio_file)

# ---- Preview of preset ----
st.divider()
st.subheader(f"✨ 当前风格: {preset}")
st.info(EFFECT_PRESETS[preset]["description"])

# ---- Generate button ----
st.divider()

if video_files:
    if st.button("🎬 生成卡点视频", type="primary", use_container_width=True):
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = None
            if use_library and selected_music:
                audio_path = os.path.join(music_dir, selected_music)
            elif audio_file:
                audio_path = os.path.join(tmpdir, f"input_audio{Path(audio_file.name).suffix}")
                with open(audio_path, "wb") as f:
                    f.write(audio_file.read())

            results = []
            total = len(video_files)

            for idx, video_file in enumerate(video_files):
                st.subheader(f"🎬 处理中 ({idx + 1}/{total}): {video_file.name}")

                video_path = os.path.join(tmpdir, f"input_video_{idx}{Path(video_file.name).suffix}")
                with open(video_path, "wb") as f:
                    f.write(video_file.read())

                output_path = os.path.join(tmpdir, f"output_beatcut_{idx}.mp4")

                progress_bar = st.progress(0, "分析节拍中...")
                status_text = st.empty()

                def make_progress_callback(bar, status):
                    def update(p):
                        bar.progress(p, f"处理中... {int(p * 100)}%")
                    return update

                update_progress = make_progress_callback(progress_bar, status_text)

                try:
                    status_text.info("正在检测节拍...")
                    result = create_beat_video(
                        video_path=video_path,
                        audio_path=audio_path,
                        output_path=output_path,
                        preset=preset,
                        output_fps=fps,
                        output_resolution=output_resolution,
                        max_duration=max_duration,
                        progress_callback=update_progress,
                        keep_original_audio=keep_audio,
                        trim_to_video=trim_to_video,
                    )

                    progress_bar.progress(1.0, "完成！")
                    status_text.success(f"✅ {video_file.name} 生成成功！")

                    st.video(result)

                    with open(result, "rb") as f:
                        st.download_button(
                            label=f"⬇️ 下载 {video_file.name}",
                            data=f,
                            file_name=f"beatcut_{preset}_{Path(video_file.name).stem}.mp4",
                            mime="video/mp4",
                            key=f"download_{idx}",
                        )

                    results.append(result)
                    st.divider()

                except Exception as e:
                    status_text.error(f"❌ {video_file.name} 生成失败: {e}")
                    st.exception(e)
                    st.divider()

            if results:
                st.success(f"🎉 全部完成！共生成 {len(results)} 个视频")
else:
    st.info("👆 请先上传视频文件（支持多选）")

# ---- Footer ----
st.divider()
st.caption("BeatCut — 一个人也能做出酷炫的卡点视频 🚀")
