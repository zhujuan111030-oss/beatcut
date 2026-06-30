"""Streamlit web app for BeatCut - beat-synced video editor.

Run with:
    streamlit run app.py
"""

import os
import tempfile
from pathlib import Path

import streamlit as st
from moviepy import VideoFileClip, concatenate_videoclips

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
        "选择视频文件（支持多选，将合并为一段）",
        type=["mp4", "mov", "avi", "mkv", "webm"],
        accept_multiple_files=True,
        key="video",
    )
    if video_files:
        if len(video_files) > 1:
            st.caption(f"已选择 {len(video_files)} 个视频，将按顺序合并")
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

            # ---- Step 1: Merge videos if multiple ----
            if len(video_files) > 1:
                status_text = st.empty()
                status_text.info(f"正在合并 {len(video_files)} 个视频...")
                merge_clips = []
                for vf in video_files:
                    tmp_path = os.path.join(tmpdir, vf.name)
                    with open(tmp_path, "wb") as f:
                        f.write(vf.read())
                    clip = VideoFileClip(tmp_path)
                    merge_clips.append(clip)
                merged_clip = concatenate_videoclips(merge_clips)
                video_path = os.path.join(tmpdir, "merged_video.mp4")
                merged_clip.write_videofile(video_path, fps=30, codec="libx264", audio_codec="aac", logger=None)
                for c in merge_clips:
                    c.close()
                merged_clip.close()
                status_text.success(f"合并完成，总时长 {merged_clip.duration:.1f}s")
            else:
                video_path = os.path.join(tmpdir, video_files[0].name)
                with open(video_path, "wb") as f:
                    f.write(video_files[0].read())

            output_path = os.path.join(tmpdir, "output_beatcut.mp4")

            progress_bar = st.progress(0, "分析节拍中...")
            status_text = st.empty()

            def update_progress(p):
                progress_bar.progress(p, f"处理中... {int(p * 100)}%")

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
                status_text.success("✅ 生成成功！")

                st.video(result)

                with open(result, "rb") as f:
                    st.download_button(
                        label="⬇️ 下载视频",
                        data=f,
                        file_name=f"beatcut_{preset}.mp4",
                        mime="video/mp4",
                    )

            except Exception as e:
                status_text.error(f"❌ 生成失败: {e}")
                st.exception(e)
else:
    st.info("👆 请先上传视频文件（支持多选，多个视频将自动合并）")

# ---- Footer ----
st.divider()
st.caption("BeatCut — 一个人也能做出酷炫的卡点视频 🚀")
