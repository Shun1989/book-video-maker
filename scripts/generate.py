#!/usr/bin/env python3
"""
拆书成视频 - 核心脚本
五步流水线：文案生成 → 豆包出图 → edge-tts 语音 → FFmpeg 渲染片段 → 合并
"""

import argparse
import json
import os
import subprocess
import sys
import time
import asyncio
from pathlib import Path

import requests

# ============================================================
# 配置
# ============================================================

ARK_API_KEY = os.environ.get("ARK_API_KEY", "")
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
ARK_IMAGE_MODEL = "doubao-seedream-5-0-260128"

# 出图尺寸：优先 9:16 竖屏，API 不支持时降级 1:1
# 1440×2560 = 3,686,400 像素（豆包最低线），精确 9:16
# 1620×2880 = 4,665,600 像素，精确 9:16，安全余量
# 2048×2048 = 4,194,304 像素，1:1 降级方案（需配竖屏构图提示词）
IMAGE_SIZES_PORTRAIT = ["1440x2560", "1620x2880"]
IMAGE_SIZE_FALLBACK = "2048x2048"

# 字体路径（验证存在用原始路径，FFmpeg drawtext 用转义路径）
CN_FONT_PATH = "C:/Windows/Fonts/msyhbd.ttc"
EN_FONT_PATH = "C:/Windows/Fonts/arial.ttf"
CN_FONT = "C\\:/Windows/Fonts/msyhbd.ttc"
EN_FONT = "C\\:/Windows/Fonts/arial.ttf"

STYLE_PREFIXES = {
    "cinematic": "cinematic still, dramatic lighting, film grain, shallow depth of field, golden hour,",
    "minimalist": "minimalist illustration, clean composition, pastel colors, negative space, soft light,",
    "watercolor": "watercolor painting, soft wash, hand-drawn texture, warm tones, artistic,",
    "cyberpunk": "cyberpunk style, neon lights, dark atmosphere, futuristic city, high contrast,",
    "vintage": "vintage film photograph, retro tones, grainy texture, warm sepia, nostalgic,",
}

# ============================================================
# 内置文案库（当 ARK 文本模型不可用时使用）
# ============================================================

BUILTIN_SCRIPTS = {
    "被讨厌的勇气": [
        {"cn": "一本书告诉你，为什么越在意别人的人越不自由", "en": "This book tells you why caring too much makes you unfree", "prompt": "a person trapped in a web of strings connecting to faceless figures, dramatic lighting, dark and oppressive, cinematic close-up"},
        {"cn": "阿德勒说，一切烦恼都来自人际关系", "en": "Adler says all problems come from relationships", "prompt": "a lonely figure standing in a crowd of blurred faces, isolation contrast, cinematic wide shot, moody blue tones"},
        {"cn": "我们不是被过去决定，而是被目标驱动", "en": "We are not determined by the past, but driven by goals", "prompt": "a person looking up at a distant light on a dark path, teleology concept, cinematic landscape, warm light ahead"},
        {"cn": "课题分离，是这本书最锋利的一把刀", "en": "Separation of tasks is the sharpest knife in this book", "prompt": "a hand holding a glowing knife cutting through entangled strings, metaphor for boundaries, dramatic close-up, golden light"},
        {"cn": "这是谁的课题？问完这句，你就不纠结了", "en": "Whose task is this? One question to end your struggle", "prompt": "a person standing at a crossroads with two diverging paths, decision moment, aerial shot, warm sunset light, cinematic"},
        {"cn": "不要活在对别人的期待里", "en": "Stop living for others' expectations", "prompt": "a person removing a mask revealing their true face, freedom concept, dramatic lighting, dark background, cinematic portrait"},
        {"cn": "自由就是被别人讨厌的勇气", "en": "Freedom is the courage to be disliked", "prompt": "a person standing alone on a mountain peak facing the wind, freedom and solitude, epic wide shot, golden hour, cinematic"},
        {"cn": "你的人生不是别人给你出的考卷", "en": "Your life is not an exam others wrote for you", "prompt": "a blank exam paper being torn apart, hands breaking free, dramatic motion, close-up, cinematic lighting"},
        {"cn": "此时此刻，才是你唯一能改变的", "en": "Here and now is all you can change", "prompt": "a person standing in the present moment with past fading behind and future ahead, time concept, cinematic wide shot, warm light"},
        {"cn": "关注我，每天一本好书，给你改变的勇气", "en": "Follow me for daily book recommendations and courage to change", "prompt": "a stack of books with warm light emanating from them, invitation to read, cozy atmosphere, cinematic still life, golden light"},
    ],
    "穷爸爸富爸爸": [
        {"cn": "一本书讲清穷人和富人最根本的区别在哪", "en": "One book explains the fundamental difference between rich and poor", "prompt": "split composition: left side a person counting coins at a dim desk, right side a person reviewing financial charts on a bright screen, contrast lighting, cinematic"},
        {"cn": "穷人为钱工作，富人让钱为自己工作", "en": "The poor work for money, the rich make money work for them", "prompt": "split composition: left a person pushing a heavy wheel, right coins and gears turning by themselves, metaphor, dramatic lighting"},
        {"cn": "你以为的资产，其实是负债", "en": "What you think is an asset is actually a liability", "prompt": "a person holding a golden key that reveals chains underneath, metaphor for hidden debt, dramatic close-up, dark and golden tones"},
        {"cn": "房子不是资产，这个观念颠覆了大多数人", "en": "Your house is not an asset, this idea shocks most people", "prompt": "a beautiful house with roots showing chains dragging it down, surreal concept art, dramatic lighting, cinematic wide shot"},
        {"cn": "穷人买负债，富人买资产，差别就这么简单", "en": "The poor buy liabilities, the rich buy assets, it's that simple", "prompt": "split shopping carts: one filled with depreciating goods, one with growing plants and gold coins, contrast, clean composition, cinematic"},
        {"cn": "恐惧让你留在舒适区，贪婪让你追涨杀跌", "en": "Fear keeps you in comfort zone, greed makes you chase bubbles", "prompt": "a person frozen at a cliff edge while others run toward a mirage, emotional landscape, dramatic sky, cinematic wide shot"},
        {"cn": "财商不是天赋，是学校不教但必须自学的技能", "en": "Financial IQ isn't innate, it's a skill schools don't teach", "prompt": "a person studying financial books at night under a desk lamp while a graduation cap sits unused, cinematic still life, warm light"},
        {"cn": "被动收入才是真正的自由", "en": "Passive income is true freedom", "prompt": "a person relaxing in a hammock while small coins rain down from a tree, freedom concept, warm golden light, idyllic cinematic scene"},
        {"cn": "不是赚得多就富有，而是留得住才富有", "en": "Wealth isn't about earning more, it's about keeping more", "prompt": "a person with a bucket full of water while another has a bucket with holes, metaphor for savings, clean minimalist composition, dramatic lighting"},
        {"cn": "关注我，读懂财富自由的底层逻辑", "en": "Follow me to understand the logic of financial freedom", "prompt": "a person climbing a staircase made of books toward a bright horizon, progress and learning, cinematic wide shot, golden hour, inspirational"},
    ],
    "原子习惯": [
        {"cn": "一本书告诉你，为什么改不掉坏习惯", "en": "This book explains why you can't break bad habits", "prompt": "a person trying to push a massive boulder uphill while small pebbles roll back, Sisyphus metaphor, dramatic lighting, cinematic wide shot"},
        {"cn": "不要定大目标，要建小系统", "en": "Don't set big goals, build small systems", "prompt": "a comparison: left a towering mountain peak, right small stepping stones forming a path, metaphor for systems thinking, clean composition, cinematic"},
        {"cn": "每天进步百分之一，一年后强37倍", "en": "1% better every day, 37 times stronger in a year", "prompt": "a small plant growing exponentially into a massive tree over time, growth concept, time-lapse feel, golden hour, cinematic wide shot"},
        {"cn": "习惯是复利，不是加法", "en": "Habits are compound interest, not addition", "prompt": "a single coin multiplying into a pile, compound growth metaphor, dramatic close-up, golden and warm tones, cinematic still life"},
        {"cn": "你不会超越你的系统，你只会掉到你的系统之下", "en": "You never rise above your systems, you fall below them", "prompt": "a person standing on a platform of good habits looking down at a pit of bad habits, foundation metaphor, dramatic lighting, cinematic"},
        {"cn": "四步循环：提示、渴望、回应、奖励", "en": "Four-step loop: cue, craving, response, reward", "prompt": "a circular loop diagram made of physical objects: a bell, a heart, a hand, a gift box, clean minimalist, dramatic lighting, cinematic still life"},
        {"cn": "环境设计比意志力强一百倍", "en": "Environment design is 100x stronger than willpower", "prompt": "a person surrounded by healthy choices on one side and temptations on the other, the healthy side is brighter and closer, contrast, cinematic"},
        {"cn": "让好习惯变得容易，让坏习惯变得困难", "en": "Make good habits easy, bad habits hard", "prompt": "a smooth path leading to a garden vs a thorny path leading to junk food, choice metaphor, aerial shot, dramatic contrast, cinematic"},
        {"cn": "身份决定行为：先成为那个人，再做那件事", "en": "Identity drives behavior: become the person first, then do the thing", "prompt": "a person looking into a mirror and seeing their future self, identity transformation, dramatic lighting, cinematic portrait, golden light"},
        {"cn": "关注我，每天一个改变人生的小习惯", "en": "Follow me for one life-changing habit each day", "prompt": "a person placing a single small stone on top of others, building something great, patience and consistency, warm golden light, cinematic close-up"},
    ],
}


def generate_script(book_name, num_sentences=12, style="cinematic"):
    """生成文案。优先用内置库，否则用 ARK 文本模型（如果可用）"""
    print(f"\n[1/5] 生成文案：《{book_name}》，{num_sentences} 句，风格={style}")

    # 先查内置库
    for key, scripts in BUILTIN_SCRIPTS.items():
        if key in book_name or book_name in key:
            if num_sentences <= len(scripts):
                result = scripts[:num_sentences]
            else:
                result = scripts + scripts[:num_sentences - len(scripts)]
            print(f"  ✅ 命中内置文案库，{len(result)} 句")
            for i, s in enumerate(result):
                print(f"  [{i+1}] {s.get('cn', '')}")
            return result

    # 尝试 ARK 文本模型
    print(f"  内置库未命中，尝试 ARK 文本模型...")
    ark_scripts = _generate_script_via_ark(book_name, num_sentences, style)
    if ark_scripts:
        return ark_scripts

    # 最终兜底：用通用模板
    print(f"  ⚠️ ARK 文本模型不可用，使用通用模板")
    return _generate_generic_script(book_name, num_sentences, style)


def _generate_script_via_ark(book_name, num_sentences, style):
    """尝试用 ARK 文本模型生成文案（需要正确的模型 ID）"""
    if not ARK_API_KEY:
        return None

    # 尝试多个可能的模型 ID
    text_models = [
        "doubao-1-5-pro-256k-250115",
        "doubao-1-5-pro-32k-250115",
        "doubao-pro-256k-241028",
    ]

    style_hint = STYLE_PREFIXES.get(style, STYLE_PREFIXES["cinematic"])

    prompt = f"""你是一个书单号短视频的文案策划师。书名：《{book_name}》。

请写 {num_sentences} 句视频文案，每句 15-25 字，口语化。结构：开头介绍书名，中间按主题展开，结尾行动引导。

给每句配英文翻译和画图提示词（英文）。风格参考：{style_hint}

以 JSON 数组输出，每元素含 cn/en/prompt 三字段。只输出 JSON。"""

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ARK_API_KEY}",
    }

    for model in text_models:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是专业的短视频文案策划师。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.8,
        }
        try:
            resp = requests.post(
                f"{ARK_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            if resp.status_code != 200:
                continue
            content = resp.json()["choices"][0]["message"]["content"].strip()
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()
            script_data = json.loads(content)
            print(f"  ✅ ARK 模型 {model} 生成 {len(script_data)} 句")
            return script_data
        except Exception:
            continue
    return None


def _generate_generic_script(book_name, num_sentences, style):
    """通用模板兜底"""
    templates = [
        {"cn": f"今天带你读懂《{book_name}》", "en": f"Today let's understand this book", "prompt": "a book opening with light pouring out of the pages, magical, dramatic lighting, cinematic close-up"},
        {"cn": "这本书改变了很多人的思维方式", "en": "This book changed how many people think", "prompt": "a person's head with gears turning inside, transformation concept, dramatic lighting, cinematic"},
        {"cn": "核心观点只有一句话，但能受用一辈子", "en": "One core idea, a lifetime of benefit", "prompt": "a single glowing coin among many dark ones, value concept, dramatic close-up, cinematic"},
        {"cn": "读懂这本书，少走十年弯路", "en": "Read this book, save ten years of detours", "prompt": "a person choosing a shortcut through a forest while others take the long road, path metaphor, aerial shot, cinematic"},
        {"cn": "不是因为难才不做，是因为不做才难", "en": "It's not hard so you don't do it, you don't do it so it's hard", "prompt": "a person facing a wall that turns out to be a door, perspective shift, dramatic lighting, cinematic"},
        {"cn": "这本书最狠的一点是它戳破了你的借口", "en": "The cruelest part is how it punctures your excuses", "prompt": "a balloon labeled with excuses being popped by a needle, metaphor, dramatic close-up, cinematic"},
        {"cn": "合上书的那一刻，你的世界变了", "en": "The moment you close the book, your world changes", "prompt": "a person closing a book with light emanating from between the pages, transformation, cinematic, golden light"},
        {"cn": "不是读书没用，是你没读对书", "en": "It's not that reading is useless, you read the wrong books", "prompt": "a person selecting one glowing book from a shelf of dusty ones, choice metaphor, dramatic lighting, cinematic"},
        {"cn": "一本好书顶一百本烂书", "en": "One good book is worth a hundred bad ones", "prompt": "one golden book standing tall among a pile of gray books, quality metaphor, dramatic lighting, cinematic still life"},
        {"cn": "关注我，每天一本改变认知的好书", "en": "Follow me for daily books that change your mind", "prompt": "a person offering a book to the viewer, warm invitation, golden hour light, cinematic portrait"},
    ]
    if num_sentences <= len(templates):
        return templates[:num_sentences]
    return templates + templates[:num_sentences - len(templates)]


# ============================================================
# 第二步：豆包 API 生成配图
# ============================================================

def generate_image(prompt, output_path, style_prefix=""):
    """调用豆包文生图 API，优先 9:16 竖屏，降级 1:1"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ARK_API_KEY}",
    }

    # 优先尝试 9:16 竖屏尺寸
    for size in IMAGE_SIZES_PORTRAIT:
        full_prompt = f"{style_prefix} {prompt}".strip()
        payload = {
            "model": ARK_IMAGE_MODEL,
            "prompt": full_prompt,
            "size": size,
            "response_format": "url",
        }
        for attempt in range(2):
            try:
                resp = requests.post(
                    f"{ARK_BASE_URL}/images/generations",
                    headers=headers,
                    json=payload,
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
                if "data" in data and len(data["data"]) > 0:
                    img_url = data["data"][0].get("url")
                    if img_url:
                        img_data = requests.get(img_url, timeout=60).content
                        with open(output_path, "wb") as f:
                            f.write(img_data)
                        return True
                err = data.get("error", {}).get("message", str(data))
                print(f"  ⚠️ 出图异常 ({size}): {err}")
            except Exception as e:
                print(f"  ⚠️ 第 {attempt+1} 次出图失败 ({size}): {e}")
            if attempt < 1:
                time.sleep(5)

    # 降级：1:1 + 竖屏构图提示
    print(f"  ⚠️ 9:16 尺寸不可用，降级 1:1 + 竖屏构图提示")
    full_prompt = f"vertical 9:16 composition, {style_prefix} {prompt}".strip()
    payload = {
        "model": ARK_IMAGE_MODEL,
        "prompt": full_prompt,
        "size": IMAGE_SIZE_FALLBACK,
        "response_format": "url",
    }
    for attempt in range(3):
        try:
            resp = requests.post(
                f"{ARK_BASE_URL}/images/generations",
                headers=headers,
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            if "data" in data and len(data["data"]) > 0:
                img_url = data["data"][0].get("url")
                if img_url:
                    img_data = requests.get(img_url, timeout=60).content
                    with open(output_path, "wb") as f:
                        f.write(img_data)
                    return True
            err = data.get("error", {}).get("message", str(data))
            print(f"  ⚠️ 降级出图异常: {err}")
        except Exception as e:
            print(f"  ⚠️ 降级第 {attempt+1} 次出图失败: {e}")
        if attempt < 2:
            time.sleep(5)
    return False


def generate_all_images(script_data, img_dir, style="cinematic"):
    """为每句文案生成配图"""
    print(f"\n[2/5] 生成配图：{len(script_data)} 张")
    style_prefix = STYLE_PREFIXES.get(style, STYLE_PREFIXES["cinematic"])
    img_paths = []

    for i, item in enumerate(script_data):
        prompt = item.get("prompt", "")
        img_path = os.path.join(img_dir, f"img_{i:03d}.jpg")
        print(f"  [{i+1}/{len(script_data)}] {prompt[:60]}...")
        if generate_image(prompt, img_path, style_prefix):
            img_paths.append(img_path)
            print(f"      ✅ {os.path.getsize(img_path)//1024}KB")
        else:
            print(f"      ❌ 出图失败，用纯色占位")
            _make_placeholder(img_path, 1440, 2560, i)
            img_paths.append(img_path)
        time.sleep(1)

    return img_paths


def _make_placeholder(path, w, h, idx):
    """生成纯色占位图"""
    colors = [(30, 50, 80), (60, 40, 70), (40, 60, 50), (70, 50, 40)]
    c = colors[idx % len(colors)]
    try:
        from PIL import Image
        img = Image.new("RGB", (w, h), c)
        img.save(path, "JPEG", quality=85)
    except Exception:
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"color=c=0x{c[0]:02x}{c[1]:02x}{c[2]:02x}:s={w}x{h}:d=1",
            "-frames:v", "1", path
        ], capture_output=True)


# ============================================================
# 第三步：edge-tts 语音合成
# ============================================================

async def _generate_voice_async(text, output_path, voice="zh-CN-YunxiNeural"):
    """用 edge-tts 生成语音"""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    with open(output_path, "wb") as f:
        for c in chunks:
            f.write(c)


def generate_voice(text, output_path, voice="zh-CN-YunxiNeural"):
    """同步包装：edge-tts 生成单句语音"""
    for attempt in range(3):
        try:
            asyncio.run(_generate_voice_async(text, output_path, voice))
            if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
                return True
        except Exception as e:
            print(f"  ⚠️ 语音第 {attempt+1} 次失败: {e}")
        if attempt < 2:
            time.sleep(2)
    return False


def generate_all_voices(script_data, voice_dir, voice="zh-CN-YunxiNeural"):
    """逐句生成语音，返回 [(voice_path, duration), ...]"""
    print(f"\n[3/5] 生成语音：{len(script_data)} 句，voice={voice}")
    voice_data = []

    for i, item in enumerate(script_data):
        text = item.get("cn", "")
        voice_path = os.path.join(voice_dir, f"voice_{i:03d}.mp3")
        print(f"  [{i+1}/{len(script_data)}] {text[:30]}...")
        if generate_voice(text, voice_path, voice):
            duration = get_audio_duration(voice_path)
            voice_data.append((voice_path, duration))
            print(f"      ✅ {duration:.1f}s")
        else:
            print(f"      ❌ 语音失败")
            voice_data.append((None, 3.0))
        time.sleep(0.5)

    return voice_data


def get_audio_duration(audio_path):
    """用 ffprobe 获取音频时长"""
    if not audio_path or not os.path.exists(audio_path):
        return 3.0
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True, timeout=10
        )
        return float(result.stdout.strip())
    except Exception:
        return 3.0


# ============================================================
# 第四步：FFmpeg 渲染视频片段
# ============================================================

def create_segment(bg_path, voice_path, text_cn, text_en, duration, output_path, segment_idx=0):
    """渲染单个视频片段：背景图 + 语音 + 字幕 + Ken Burns"""
    def escape_text(t):
        # FFmpeg drawtext 在单引号字符串内不支持转义单引号
        # 所以直接把撇号替换为 unicode 右单引号
        t = t.replace("'", "\u2019")
        t = t.replace("\\", "\\\\").replace(":", "\\:").replace("%", "\\%")
        return t

    cn_safe = escape_text(text_cn)
    en_safe = escape_text(text_en)

    # 中文字幕
    cn_filter = (
        f"drawtext=text='{cn_safe}':fontfile='{CN_FONT}':fontsize=52:"
        f"fontcolor=white:x=(w-text_w)/2:y=(h*0.72):"
        f"shadowx=3:shadowy=3:shadowcolor=black@0.8:"
        f"borderw=2:bordercolor=black@0.5"
    )

    # 英文字幕
    en_filter = (
        f"drawtext=text='{en_safe}':fontfile='{EN_FONT}':fontsize=32:"
        f"fontcolor=white@0.85:x=(w-text_w)/2:y=(h*0.72)+62:"
        f"shadowx=2:shadowy=2:shadowcolor=black@0.6"
    )

    # Ken Burns 镜头移动：4 个方向交替
    # 关键修复：使用 force_original_aspect_ratio=increase 防止 1:1 图片被拉伸变形
    # 两阶段裁切：
    #   1) scale 到覆盖 1188×2112 → center crop 到精确 1188×2112（去除 1:1 降级图多余宽度）
    #   2) Ken Burns 从 1188×2112 裁切 1080×1920，偏移范围 x∈[0,108] y∈[0,192]
    SCALE_W, SCALE_H = 1188, 2112
    CROP_W, CROP_H = 1080, 1920
    MAX_X = SCALE_W - CROP_W   # 108
    MAX_Y = SCALE_H - CROP_H   # 192

    # 阶段1：无 distortion 缩放 + 居中裁切到统一尺寸
    base = f"scale={SCALE_W}:{SCALE_H}:force_original_aspect_ratio=increase,crop={SCALE_W}:{SCALE_H}:'(iw-{SCALE_W})/2':'(ih-{SCALE_H})/2'"

    directions = ["right", "left", "down", "up"]
    direction = directions[segment_idx % 4]

    if direction == "right":
        ken_burns = f"{base},crop={CROP_W}:{CROP_H}:'min(t*60,{MAX_X})':'({MAX_Y}/2)'"
    elif direction == "left":
        ken_burns = f"{base},crop={CROP_W}:{CROP_H}:'max({MAX_X}-t*60,0)':'({MAX_Y}/2)'"
    elif direction == "down":
        ken_burns = f"{base},crop={CROP_W}:{CROP_H}:'({MAX_X}/2)':'min(t*60,{MAX_Y})'"
    else:  # up
        ken_burns = f"{base},crop={CROP_W}:{CROP_H}:'({MAX_X}/2)':'max({MAX_Y}-t*60,0)'"

    vf = f"{ken_burns},{cn_filter},{en_filter}"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", bg_path,
        "-t", str(max(duration, 1.0)),
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-r", "30", "-preset", "fast", "-crf", "23",
        output_path
    ]

    if voice_path and os.path.exists(voice_path):
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", bg_path,
            "-i", voice_path,
            "-t", str(max(duration, 1.0)),
            "-vf", vf,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-r", "30", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k", "-shortest",
            output_path
        ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(f"  ⚠️ FFmpeg 渲染失败: {result.stderr[-200:]}")
        return False
    return True


def render_all_segments(script_data, img_paths, voice_data, seg_dir):
    """渲染所有视频片段"""
    print(f"\n[4/5] 渲染视频片段：{len(script_data)} 个")
    seg_paths = []

    for i, item in enumerate(script_data):
        bg = img_paths[i] if i < len(img_paths) else None
        vp, dur = voice_data[i] if i < len(voice_data) else (None, 3.0)
        seg_path = os.path.join(seg_dir, f"seg_{i:03d}.mp4")

        print(f"  [{i+1}/{len(script_data)}] {dur:.1f}s -> {os.path.basename(seg_path)}")

        if bg and os.path.exists(bg):
            if create_segment(bg, vp, item.get("cn", ""), item.get("en", ""), dur, seg_path, i):
                seg_paths.append(seg_path)
                print(f"      ✅ {os.path.getsize(seg_path)//1024}KB")
            else:
                print(f"      ❌ 渲染失败")
                return None
        else:
            print(f"      ❌ 缺少背景图")
            return None

    return seg_paths


# ============================================================
# 第五步：合并所有片段
# ============================================================

def merge_segments(seg_paths, voice_paths, output_path):
    """合并视频片段 + 音频"""
    print(f"\n[5/5] 合并 {len(seg_paths)} 个片段")

    work_dir = os.path.dirname(output_path)
    concat_file = os.path.join(work_dir, "concat_list.txt")

    with open(concat_file, "w", encoding="utf-8") as f:
        for sp in seg_paths:
            safe_path = sp.replace("\\", "/")
            f.write(f"file '{safe_path}'\n")

    # 合并视频（重编码方式更稳定）
    merged_video = os.path.join(work_dir, "merged_video.mp4")
    cmd1 = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-r", "30", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        merged_video
    ]
    r1 = subprocess.run(cmd1, capture_output=True, text=True, timeout=300)
    if r1.returncode != 0:
        print(f"  ❌ 合并失败: {r1.stderr[-300:]}")
        return False

    # 合并语音
    valid_voices = [vp for vp in voice_paths if vp and os.path.exists(vp)]
    voice_concat_file = os.path.join(work_dir, "voice_concat.txt")
    if valid_voices:
        voice_concat_file = os.path.join(work_dir, "voice_concat.txt")
        with open(voice_concat_file, "w", encoding="utf-8") as f:
            for vp in valid_voices:
                safe_path = vp.replace("\\", "/")
                f.write(f"file '{safe_path}'\n")

        merged_audio = os.path.join(work_dir, "merged_audio.mp3")
        cmd2 = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", voice_concat_file,
            "-c:a", "libmp3lame", "-b:a", "192k",
            merged_audio
        ]
        r2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=60)
        if r2.returncode == 0:
            # 合并视频和音频
            cmd3 = [
                "ffmpeg", "-y",
                "-i", merged_video,
                "-i", merged_audio,
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest", output_path
            ]
            r3 = subprocess.run(cmd3, capture_output=True, text=True, timeout=120)
            if r3.returncode != 0:
                os.replace(merged_video, output_path)
            else:
                os.remove(merged_video)
                os.remove(merged_audio)
        else:
            os.replace(merged_video, output_path)
    else:
        os.replace(merged_video, output_path)

    for tmp in [concat_file, voice_concat_file]:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass

    final_size = os.path.getsize(output_path) // 1024
    print(f"  ✅ 最终成片: {output_path} ({final_size}KB)")
    return True


# ============================================================
# 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="拆书成视频：给一本书名，生成一条竖屏书单短视频")
    parser.add_argument("--book", required=True, help="书名（中文）")
    parser.add_argument("--style", default="cinematic",
                        choices=["cinematic", "minimalist", "watercolor", "cyberpunk", "vintage"],
                        help="画面风格")
    parser.add_argument("--voice", default="zh-CN-YunxiNeural",
                        help="edge-tts 语音名称")
    parser.add_argument("--sentences", type=int, default=10, help="文案句数（8-20）")
    parser.add_argument("--output", default="output", help="输出目录")
    parser.add_argument("--skip-images", action="store_true",
                        help="跳过出图，用已有图片")
    parser.add_argument("--skip-gen-script", action="store_true",
                        help="跳过文案生成，用已有的 JSON")
    args = parser.parse_args()

    # 从 .env 文件加载 ARK_API_KEY
    if not ARK_API_KEY:
        env_path = os.path.expanduser("~/.baoyu-skills/.env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("ARK_API_KEY="):
                        key = line.split("=", 1)[1]
                        os.environ["ARK_API_KEY"] = key
                        globals()["ARK_API_KEY"] = key
                        break

    if not ARK_API_KEY:
        print("❌ 缺少 ARK_API_KEY 环境变量")
        sys.exit(1)

    # 验证工具
    for tool in ["ffmpeg", "ffprobe"]:
        try:
            subprocess.run([tool, "-version"], capture_output=True, timeout=5)
        except Exception:
            print(f"❌ 缺少工具: {tool}")
            sys.exit(1)

    for font in [CN_FONT_PATH, EN_FONT_PATH]:
        if not os.path.exists(font):
            print(f"❌ 缺少字体: {font}")
            sys.exit(1)

    try:
        import edge_tts
    except ImportError:
        print("❌ 缺少 edge-tts，请运行: pip install edge-tts")
        sys.exit(1)

    # 准备目录
    book_slug = args.book.replace(" ", "_").replace("/", "_").replace("：", "_").replace(":", "_")
    base_dir = os.path.abspath(args.output)
    work_dir = os.path.join(base_dir, book_slug)
    img_dir = os.path.join(work_dir, "images")
    voice_dir = os.path.join(work_dir, "voices")
    seg_dir = os.path.join(work_dir, "segments")
    script_path = os.path.join(work_dir, f"{book_slug}_script.json")
    output_path = os.path.join(base_dir, f"{book_slug}_final.mp4")

    for d in [base_dir, work_dir, img_dir, voice_dir, seg_dir]:
        os.makedirs(d, exist_ok=True)

    print(f"{'='*60}")
    print(f"  拆书成视频")
    print(f"  书名: 《{args.book}》")
    print(f"  风格: {args.style}")
    print(f"  语音: {args.voice}")
    print(f"  句数: {args.sentences}")
    print(f"  输出: {output_path}")
    print(f"{'='*60}")

    start_time = time.time()

    # Step 1: 文案
    if args.skip_gen_script and os.path.exists(script_path):
        print(f"\n[1/5] 跳过文案生成，使用已有 JSON: {script_path}")
        with open(script_path, "r", encoding="utf-8") as f:
            script_data = json.load(f)
    else:
        script_data = generate_script(args.book, args.sentences, args.style)
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(script_data, f, ensure_ascii=False, indent=2)
        print(f"  📝 文案已保存: {script_path}")

    # Step 2: 配图
    if args.skip_images:
        print(f"\n[2/5] 跳过出图，使用已有图片")
        img_paths = []
        for i in range(len(script_data)):
            img_path = os.path.join(img_dir, f"img_{i:03d}.jpg")
            if os.path.exists(img_path):
                img_paths.append(img_path)
            else:
                _make_placeholder(img_path, 1440, 2560, i)
                img_paths.append(img_path)
    else:
        img_paths = generate_all_images(script_data, img_dir, args.style)

    # Step 3: 语音
    voice_data = generate_all_voices(script_data, voice_dir, args.voice)
    voice_paths = [vd[0] for vd in voice_data]

    # Step 4: 渲染片段
    seg_paths = render_all_segments(script_data, img_paths, voice_data, seg_dir)
    if not seg_paths:
        print("❌ 渲染失败")
        sys.exit(1)

    # Step 5: 合并
    success = merge_segments(seg_paths, voice_paths, output_path)

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    if success:
        total_duration = sum(vd[1] for vd in voice_data)
        print(f"  ✅ 完成！耗时 {elapsed:.0f} 秒")
        print(f"  📹 成片: {output_path}")
        print(f"  ⏱️ 时长: 约 {total_duration:.0f} 秒")
        print(f"  📦 大小: {os.path.getsize(output_path)//1024}KB")
    else:
        print(f"  ❌ 失败")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
