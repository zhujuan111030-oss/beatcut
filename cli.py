
#!/usr/bin/env python3
"""Command-line interface for BeatCut.

Usage:
    python cli.py video.mp4 --music song.mp3 --preset energy
    python cli.py video.mp4 --music song.mp3 --output out.mp4 --preset heavy
    python cli.py video.mp4 --batch music/*.mp3 --output-dir ./results
"""

import argparse
import os
import sys
from pathlib import Path

# Add parent to path for direct script execution
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from beatcut.video_editor import create_beat_video, batch_create
from beatcut.effects import EFFECT_PRESETS


def main():
    parser = argparse.ArgumentParser(
        description="🎬 BeatCut — 自动卡点视频编辑器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python cli.py video.mp4 --music song.mp3
  python cli.py video.mp4 --music song.mp3 --preset heavy --max-duration 30
  python cli.py video.mp4 --batch music/*.mp3 --output-dir ./my_edits
        """,
    )

    parser.add_argument("video", help="输入视频文件路径")
    parser.add_argument("--music", "-m", help="音乐文件路径 (不指定则使用视频原声)")
    parser.add_argument("--output", "-o", default="output_beatcut.mp4", help="输出文件路径")
    parser.add_argument("--preset", "-p", choices=list(EFFECT_PRESETS.keys()), default="energy",
                        help="特效风格预设")
    parser.add_argument("--fps", type=int, default=30, help="输出帧率")
    parser.add_argument("--max-duration", type=float, default=None, help="最大时长 (秒)")
    parser.add_argument("--width", type=int, default=1080, help="输出宽度")
    parser.add_argument("--height", type=int, default=1920, help="输出高度")
    parser.add_argument("--keep-audio", action="store_true", help="保留视频原声")
    parser.add_argument("--batch", help="批量模式: 音乐文件 glob 模式")

    parser.add_argument("--output-dir", default="output", help="批量输出目录")
    parser.add_argument("--list-presets", action="store_true", help="列出所有风格预设")

    args = parser.parse_args()

    if args.list_presets:
        print("\n✨ 可用风格预设:\n")
        for name, config in EFFECT_PRESETS.items():
            print(f"  {name:12s} — {config['description']}")
        return

    # Validate input
    if not os.path.exists(args.video):
        print(f"❌ 视频文件不存在: {args.video}")
        sys.exit(1)

    if args.music and not os.path.exists(args.music):
        print(f"❌ 音乐文件不存在: {args.music}")
        sys.exit(1)

    resolution = (args.width, args.height)

    if args.batch:
        # Batch mode
        import glob
        audio_paths = sorted(glob.glob(args.batch))
        if not audio_paths:
            print(f"❌ 没有找到匹配的音乐文件: {args.batch}")
            sys.exit(1)

        print(f"\n🎬 批量模式: {len(audio_paths)} 首音乐")
        print(f"   视频: {args.video}")
        print(f"   风格: {args.preset}")
        print(f"   分辨率: {resolution[0]}x{resolution[1]}\n")

        results = batch_create(
            video_path=args.video,
            audio_paths=audio_paths,
            output_dir=args.output_dir,
            preset=args.preset,
            output_resolution=resolution,
        )

        print(f"\n✅ 完成! {len(results)} 个视频已生成:")
        for r in results:
            print(f"   {r}")

    else:
        # Single mode
        if not args.music:
            print("⚠️  未指定音乐文件，将使用视频原声进行节拍检测")
            print("    (效果可能不如专门的音乐文件)")

        print(f"\n🎬 开始生成卡点视频")
        print(f"   视频: {args.video}")
        print(f"   音乐: {args.music or '(视频原声)'}")
        print(f"   风格: {args.preset}")
        print(f"   输出: {args.output}")
        print(f"   分辨率: {resolution[0]}x{resolution[1]}\n")

        result = create_beat_video(
            video_path=args.video,
            audio_path=args.music,
            output_path=args.output,
            preset=args.preset,
            output_fps=args.fps,
            output_resolution=resolution,
            max_duration=args.max_duration,
            keep_original_audio=args.keep_audio,
        )

        print(f"\n✅ 完成! 输出: {result}")


if __name__ == "__main__":
    main()
