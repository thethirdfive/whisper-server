"""诊断说话人分离（pyannote gated 模型）是否就绪。

在 worker 容器里跑：
    docker compose exec worker python scripts/check_diarization.py

它会按 worker 真实的方式去加载 DiarizationPipeline，逐步报告：
  1. HF_TOKEN / HF_ENDPOINT 是否配置
  2. 能否读到 gated 仓库元数据（间接判断条款是否已接受）
  3. 能否真正实例化分离 pipeline（最终判据）
任一步失败都会给出下一步该怎么办。
"""
import os
import sys

MODEL = os.environ.get("DIARIZE_MODEL", "pyannote/speaker-diarization-community-1")
TOKEN = os.environ.get("HF_TOKEN", "")
ENDPOINT = os.environ.get("HF_ENDPOINT", "https://huggingface.co")


def _mask(t: str) -> str:
    return f"{t[:6]}…(已配置, {len(t)} 字符)" if t else "（未配置）"


def main() -> int:
    print("=" * 60)
    print("说话人分离就绪检查")
    print("=" * 60)
    print(f"DIARIZE_MODEL : {MODEL}")
    print(f"HF_TOKEN      : {_mask(TOKEN)}")
    print(f"HF_ENDPOINT   : {ENDPOINT}")
    print("-" * 60)

    if not TOKEN:
        print("✗ 未配置 HF_TOKEN。请在 .env 设置 HF_TOKEN 后重建 worker。")
        return 1

    # 步骤 2：读 gated 仓库元数据（间接判断条款接受 + 端点可达）
    print("[2/3] 读取 gated 仓库元数据 ...")
    try:
        from huggingface_hub import model_info  # noqa: PLC0415

        info = model_info(MODEL, token=TOKEN)
        print(f"    ✓ 可访问仓库：{info.id}（条款应已接受）")
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        print(f"    ✗ 读取失败：{msg[:200]}")
        if "401" in msg or "403" in msg or "gated" in msg.lower() or "awaiting" in msg.lower():
            print("    → 多半是【条款未接受】或 token 无该仓库权限。")
            print(f"      用 HF_TOKEN 对应账号登录 https://hf.co/{MODEL} 点 Agree。")
        else:
            print("    → 可能是镜像端点不支持 gated 仓库 / 网络问题。见末尾建议。")

    # 步骤 3：真正实例化 pipeline（worker 用的就是这个）
    print("[3/3] 实例化 DiarizationPipeline ...")
    try:
        import inspect  # noqa: PLC0415

        try:
            from whisperx.diarize import DiarizationPipeline  # noqa: PLC0415
        except Exception:  # noqa: BLE001
            from whisperx import DiarizationPipeline  # type: ignore  # noqa: PLC0415

        params = inspect.signature(DiarizationPipeline.__init__).parameters
        kwargs = {"model_name": MODEL, "device": "cpu"}
        kwargs["token" if "token" in params else "use_auth_token"] = TOKEN
        DiarizationPipeline(**kwargs)
        print("    ✓ pipeline 加载成功 —— 说话人分离已就绪 ✅")
        print("=" * 60)
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"    ✗ 加载失败：{str(e)[:300]}")

    print("-" * 60)
    print("下一步建议：")
    print(f"  1. 用 HF_TOKEN 对应账号在 https://hf.co/{MODEL} 接受条款（Agree）。")
    print("  2. 若你走的是 hf-mirror.com 镜像，镜像对 gated 仓库支持不稳：")
    print("     可临时把 worker 的 HF_ENDPOINT 改回 https://huggingface.co 重试，")
    print("     或在能访问 HF 的机器上预下载该模型缓存目录拷到 HF_HOME。")
    print("  3. 实在搞不定，可用『按声道拆分』模式（双声道录音，无需该模型）。")
    print("=" * 60)
    return 2


if __name__ == "__main__":
    sys.exit(main())
