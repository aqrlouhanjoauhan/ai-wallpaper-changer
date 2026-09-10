# AI Wallpaper Changer 🎨

一个轻量级的 Windows 智能桌面壁纸生成与自动更换工具。

只需输入一句简单的中文想法（例如“雨夜赛博朋克”、“水墨孤舟”），程序会自动调用 **DeepSeek** 大模型润色并扩展为专业的生图 Prompt，随后调用 **Qwen-Image** 绘制 1920x1080 高清壁纸，并**自动设置为 Windows 当前桌面壁纸**。

---

## ✨ 特性

- **智能扩写**：集成 DeepSeek-V3.2，自动将简短想法扩写为细节丰富、构图精准的英文生图提示词。
- **多风格预设**：内置写实摄影、新海诚动漫、吉卜力手绘、东方水墨、赛博朋克、3D 极简、复古像素等多种预设。
- **自动适配与防平铺**：自动处理为标准 1920x1080 壁纸，并写入 Windows 注册表配置“拉伸填充”居中，杜绝九宫格平铺问题。
- **自动归档管理**：每次生成的壁纸与对应的 Prompt 会自动以“精简中文主题_时间戳”独立建档保存，方便回顾与二次创作。
- **持续交互**：命令行循环运行，随时输入新灵感，不闪退。

---

## 🛠️ 准备工作

本项目基于 **硅基流动 (SiliconFlow)** 提供的模型 API 驱动。

1. **注册账号并获取 API Key**：  
   👉 [点击前往硅基流动注册（含免费额度）](https://cloud.siliconflow.cn/i/OLr1TAPd)
2. 登录控制台，进入 **API 密钥** 页面，创建一个新的 API Secret Key。

---

## 📦 安装与配置

1. 克隆项目到本地：
git clone [https://github.com/aqrlouhanjoauhan/ai-wallpaper-changer.git](https://github.com/aqrlouhanjoauhan/ai-wallpaper-changer.git)
cd ai-wallpaper-changer

2. 安装 Python 依赖：
pip install requests pillow

3. 配置 API Key：
打开 ai_wallpaper.py，将顶部的 API_KEY 填入你的密钥：
API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

---

## 🚀 使用方法

在终端运行脚本：
python ai_wallpaper.py

按照提示操作：
1. 选择风格序号（例如输入 3 为日系动漫，直接回车则自由发挥）。
2. 输入画面灵感（例如：夏日晴空与电车车站）。
3. 等待约 5~10 秒，桌面壁纸将自动无缝切换！

---

## 📂 生成文件目录结构

脚本运行后会在当前目录下自动生成归档文件夹：

```text
ai-wallpaper-changer/
├── main.py
└── 赛博雨夜_1741608899/
    ├── wallpaper.png    # 1920x1080 高清壁纸
    └── prompt.txt       # 原始灵感与扩写后的最终提示词
```
