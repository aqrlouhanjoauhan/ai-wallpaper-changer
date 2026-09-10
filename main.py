import os
import re
import json
import time
import ctypes
import winreg
import requests
from pathlib import Path
from PIL import Image

# 配置信息
API_KEY = "" #硅基流动申请的api key
BASE_URL = "https://api.siliconflow.cn/v1"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

CHAT_MODEL = "Pro/deepseek-ai/DeepSeek-V3.2"
IMAGE_MODEL = "Qwen/Qwen-Image"

# 常见壁纸风格预设
STYLES = {
    "1": ("默认自由", ""),
    "2": ("写实摄影", "National Geographic style photorealistic photography, shot on 35mm lens, realistic textures, natural cinematic lighting"),
    "3": ("日系动漫", "Makoto Shinkai anime style, vibrant sky, beautiful clouds, detailed anime background art"),
    "4": ("吉卜力手绘", "Studio Ghibli aesthetic, hand-drawn watercolor illustration, nostalgic, cozy atmosphere"),
    "5": ("东方水墨", "Traditional Chinese ink wash painting, shan shui, ethereal mist, minimalistic brush strokes"),
    "6": ("赛博朋克", "Cyberpunk, neon light reflections, futuristic city, rainy night, high-tech dystopian"),
    "7": ("3D 极简立体", "3D render, C4D octane render, minimalist composition, soft clay/plastic material, clean pastel colors"),
    "8": ("复古像素", "16-bit retro pixel art, cozy aesthetic, nostalgic lighting")
}

def set_windows_wallpaper(image_path: Path):
    abs_path = str(image_path.resolve())
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, "10")
        winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, "0")
        winreg.CloseKey(key)
    except Exception as e:
        print(f"  [-] 注册表样式设置警告: {e}")

    SPI_SETDESKWALLPAPER = 20
    SPIF_UPDATEINIFILE = 0x01
    SPIF_SENDCHANGE = 0x02
    ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER, 0, abs_path, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
    )

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(" ", "_")

def polish_prompt(user_input: str, style_desc: str) -> tuple[str, str]:
    style_instruction = f"画风要求：{style_desc}。" if style_desc else "画风由用户描述决定，若未明确指定则自由发挥高质量壁纸视觉效果。"
    
    system_prompt = (
        "你是一个顶级的 AI 绘画提示词专家。你的任务是把用户的主题扩写为生图模型专用的高质量英文提示词，并提取一个极简短标题。\n"
        f"{style_instruction}\n"
        "请严格按以下 JSON 格式输出，不要包含 markdown 标记或多余文字：\n"
        '{"short_title": "4到6个字的简短描述", "prompt": "Extremely detailed English prompt for wallpaper..."}'
    )

    payload = {
        "model": CHAT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"主题：{user_input}"}
        ],
        "temperature": 0.7
    }

    resp = requests.post(f"{BASE_URL}/chat/completions", headers=HEADERS, json=payload, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"提示词润色失败 [{resp.status_code}]: {resp.text}")

    content = resp.json()["choices"][0]["message"]["content"].strip()
    json_match = re.search(r"\{[\s\S]*\}", content)
    data = json.loads(json_match.group(0)) if json_match else json.loads(content)
    
    return sanitize_filename(data.get("short_title", "Wallpaper")), data.get("prompt", user_input)

def generate_wallpaper_image(prompt: str, save_path: Path):
    payload = {
        "model": IMAGE_MODEL,
        "prompt": prompt,
        "image_size": "1024x576"
    }
    resp = requests.post(f"{BASE_URL}/images/generations", headers=HEADERS, json=payload, timeout=90)
    if resp.status_code != 200:
        raise RuntimeError(f"生图报错 [{resp.status_code}]: {resp.text}")

    image_url = resp.json()["images"][0]["url"]
    img_resp = requests.get(image_url, timeout=60)
    img_resp.raise_for_status()

    temp_path = save_path.with_name("temp_gen.png")
    with open(temp_path, "wb") as f:
        f.write(img_resp.content)

    with Image.open(temp_path) as im:
        resized = im.resize((1920, 1080), Image.Resampling.LANCZOS)
        resized.save(save_path, "PNG")

    if temp_path.exists():
        temp_path.unlink()

def main():
    script_dir = Path(__file__).resolve().parent
    print("=" * 60)
    print("      SiliconFlow 多风格 AI 壁纸生成器")
    print("=" * 60)

    while True:
        try:
            print("\n可选风格预设:")
            for k, (name, _) in STYLES.items():
                print(f" [{k}] {name}", end="  ")
            print()
            
            style_choice = input("请选择风格序号 (直接回车默认自由): ").strip()
            style_name, style_desc = STYLES.get(style_choice, STYLES["1"])

            user_input = input(f"请输入画面内容/主题 [当前风格: {style_name}] (输入 q 退出): ").strip()
            if user_input.lower() in ('q', 'exit'):
                break
            if not user_input:
                user_input = "雨后山林，薄雾晨曦"

            print("\n[1/3] 正在由 DeepSeek 润色并融入风格特征...")
            short_title, enhanced_prompt = polish_prompt(user_input, style_desc)
            print(f"  ├─ 识别目录: {short_title}")
            print(f"  └─ 扩写提示: {enhanced_prompt}")

            folder_name = f"{short_title}_{int(time.time())}"
            target_dir = script_dir / folder_name
            target_dir.mkdir(parents=True, exist_ok=True)

            print(f"\n[2/3] 正在生成高清壁纸 (1920x1080)...")
            img_path = target_dir / "wallpaper.png"
            generate_wallpaper_image(enhanced_prompt, img_path)

            prompt_path = target_dir / "prompt.txt"
            with open(prompt_path, "w", encoding="utf-8") as f:
                f.write(f"原始主题: {user_input}\n")
                f.write(f"选择风格: {style_name}\n\n")
                f.write(f"最终提示词:\n{enhanced_prompt}\n")

            print("\n[3/3] 正在应用为当前桌面壁纸...")
            set_windows_wallpaper(img_path)
            print(f"[✔] 成功更换！已归档到文件夹: {folder_name}")

        except KeyboardInterrupt:
            print("\n已退出。")
            break
        except Exception as e:
            print(f"\n[!] 出错: {e}")

if __name__ == "__main__":
    main()
