import os
import re
import json
import time
import ctypes
import winreg
import requests
from pathlib import Path
from PIL import Image, ImageEnhance

# ================= 配置区域 =================
#填写硅基流动申请的api key
API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
BASE_URL = "https://api.siliconflow.cn/v1"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 文本与生图模型配置
CHAT_MODEL = "Pro/deepseek-ai/DeepSeek-V3.2"
IMAGE_MODEL = "Qwen/Qwen-Image"  # 20B 大参数生图模型

# 风格预设
STYLES = {
    "1": ("默认自由", ""),
    "2": ("写实摄影", "photorealistic, 35mm landscape photography, master lighting, natural textures"),
    "3": ("日系动漫", "Makoto Shinkai aesthetic, anime background visual, vibrant clouds and light"),
    "4": ("吉卜力手绘", "Studio Ghibli style, nostalgic hand-drawn watercolor illustration"),
    "5": ("东方水墨", "traditional Chinese ink wash painting, shan shui style, artistic mist, minimalist"),
    "6": ("赛博朋克", "cyberpunk aesthetic, futuristic metropolis, neon glow, reflective surfaces"),
    "7": ("3D 极简", "3D octane render, minimalist composition, soft clay materials, clean pastel colors"),
    "8": ("复古像素", "16-bit retro pixel art, cozy atmosphere, nostalgic color palette"),
    "9": ("厚涂油画", "classic impasto oil painting, expressive thick brushstrokes, rich textures, fine art"),
    "10": ("美漫插画", "vintage comic book art style, bold line art, halftone dot shading, dynamic visual"),
    "11": ("暗黑奇幻", "dark fantasy concept art, mystical fog, cinematic dramatic lighting, epic scale"),
    "12": ("折纸艺术", "paper cut art, layered paper craft, intricate origami textures, soft studio lighting")
}
# ============================================

def set_windows_wallpaper(image_path: Path):
    """设置 Windows 壁纸并写入注册表（拉伸填充居中）"""
    abs_path = str(image_path.resolve())

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Control Panel\Desktop",
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, "10")
        winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, "0")
        winreg.CloseKey(key)
    except Exception as e:
        print(f"  [-] 注册表提示: {e}")

    SPI_SETDESKWALLPAPER = 20
    SPIF_UPDATEINIFILE = 0x01
    SPIF_SENDCHANGE = 0x02
    ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER, 0, abs_path, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
    )

def sanitize_filename(name: str) -> str:
    """过滤文件名非法字符"""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(" ", "_")

def polish_prompt(user_input: str, style_tag: str) -> tuple[str, str]:
    """使用 DeepSeek 丰富提示词并提炼短目录名"""
    style_rule = f"画面风格固定为：{style_tag}。" if style_tag else "风格根据用户描述自然呈现。"

    system_prompt = (
        "你是一个专业的高清壁纸提示词精炼师。\n"
        "任务：把用户的主题转化为专门用于生图模型的高画质纯英文提示词，并提炼 4-6 字中文目录名。\n"
        "画质要求：提示词自然融合 masterpiece, high quality, sharp focus, 8k resolution, crisp lines 等质感修饰词。\n"
        f"约束：{style_rule}，总长度严格控制在 40 到 60 个英文单词之间，不要堆砌无意义废话或违规词汇。\n"
        "严格按以下 JSON 格式输出，不要包含任何 markdown 代码块或多余解释：\n"
        '{"short_title": "4到6字简短主题", "prompt": "concise english prompt here"}'
    )

    payload = {
        "model": CHAT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"主题：{user_input}"}
        ],
        "temperature": 0.5
    }

    resp = requests.post(f"{BASE_URL}/chat/completions", headers=HEADERS, json=payload, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"提示词润色失败 [{resp.status_code}]: {resp.text}")

    content = resp.json()["choices"][0]["message"]["content"].strip()
    json_match = re.search(r"\{[\s\S]*\}", content)
    data = json.loads(json_match.group(0)) if json_match else json.loads(content)
    
    return sanitize_filename(data.get("short_title", "Wallpaper")), data.get("prompt", user_input)

def generate_wallpaper_image(prompt: str, save_path: Path):
    """
    优先直接请求 1920x1080 尺寸生图；
    若 API 返回尺寸不兼容错误，则自动回退至原生高清比例生成并本地无损重采样至 1920x1080。
    """
    # 尺寸降级列表（从直出 1920x1080 到高分辨率原生宽屏）
    candidate_sizes = ["1920x1080", "1280x720", "1024x576"]
    
    img_data = None
    last_err = None

    for size in candidate_sizes:
        payload = {
            "model": IMAGE_MODEL,
            "prompt": prompt,
            "image_size": size
        }

        resp = requests.post(f"{BASE_URL}/images/generations", headers=HEADERS, json=payload, timeout=90)
        if resp.status_code == 200:
            img_data = resp.json()
            break
        else:
            last_err = resp.text
            continue

    if not img_data:
        raise RuntimeError(f"生图接口报错: {last_err}")

    image_url = img_data["images"][0]["url"]
    img_resp = requests.get(image_url, timeout=60)
    img_resp.raise_for_status()

    temp_path = save_path.with_name("temp_gen.png")
    with open(temp_path, "wb") as f:
        f.write(img_resp.content)

    # 统一确保落盘为标准 1920x1080 分辨率
    with Image.open(temp_path) as im:
        if im.size != (1920, 1080):
            resized = im.resize((1920, 1080), Image.Resampling.LANCZOS)
            enhancer = ImageEnhance.Sharpness(resized)
            sharp_img = enhancer.enhance(1.15)
            sharp_img.save(save_path, "PNG", quality=100)
        else:
            im.save(save_path, "PNG", quality=100)

    if temp_path.exists():
        temp_path.unlink()

def print_style_menu():
    """打印风格菜单"""
    print("\n" + "-" * 55)
    print("可选风格预设:")
    items = list(STYLES.items())
    for i in range(0, len(items), 4):
        line = "   ".join([f"[{k}] {v[0]}" for k, v in items[i:i+4]])
        print(f"  {line}")
    print("-" * 55)

def main():
    script_dir = Path(__file__).resolve().parent
    print("=" * 60)
    print("      SiliconFlow 多风格 AI 壁纸生成与切换工具")
    print(f"  润色模型: {CHAT_MODEL}")
    print(f"  生图模型: {IMAGE_MODEL}")
    print("  退出方式: 输入 'q' 或 'exit'，也可直接按 Ctrl+C")
    print("=" * 60)

    while True:
        try:
            print_style_menu()
            style_choice = input("请选择风格序号 (直接回车默认自由): ").strip()
            style_name, style_desc = STYLES.get(style_choice, STYLES["1"])

            user_input = input(f"请输入画面灵感 [当前风格: {style_name}] (输入 q 退出): ").strip()
            if user_input.lower() in ('q', 'exit', 'quit'):
                print("程序正在退出...")
                break
            if not user_input:
                user_input = "雨后山林，薄雾晨曦"

            print("\n[1/3] 正在由 DeepSeek 进行风格化扩写...")
            short_title, enhanced_prompt = polish_prompt(user_input, style_desc)
            print(f"  ├─ 识别主题: {short_title}")
            print(f"  └─ 精炼 Prompt: {enhanced_prompt}")

            # 建立归档文件夹
            folder_name = f"{short_title}_{int(time.time())}"
            target_dir = script_dir / folder_name
            target_dir.mkdir(parents=True, exist_ok=True)

            print(f"\n[2/3] 正在调用 [{IMAGE_MODEL}] 生成 1920x1080 壁纸...")
            img_path = target_dir / "wallpaper.png"
            generate_wallpaper_image(enhanced_prompt, img_path)

            # 保存提示词归档
            prompt_path = target_dir / "prompt.txt"
            with open(prompt_path, "w", encoding="utf-8") as f:
                f.write(f"原始灵感: {user_input}\n")
                f.write(f"选择风格: {style_name}\n\n")
                f.write(f"生成提示词:\n{enhanced_prompt}\n")

            print(f"  ├─ 图片已保存至: {folder_name}/wallpaper.png")
            print(f"  └─ 提示词已保存至: {folder_name}/prompt.txt")

            print("\n[3/3] 正在设置为系统桌面壁纸...")
            set_windows_wallpaper(img_path)
            print("[✔] 换肤完成！\n")

        except KeyboardInterrupt:
            print("\n检测到退出信号，程序已退出。")
            break
        except Exception as e:
            print(f"\n[!] 运行中断: {e}")
            print("[*] 可继续输入新主题重试。")

if __name__ == "__main__":
    main()
