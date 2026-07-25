# 拆书成视频 Skill

> 给一本书名，自动生成一条 9:16 竖屏书单短视频。AI 写文案、豆包出图、edge-tts 朗读、FFmpeg 渲染字幕和镜头移动，全自动。

## 效果演示

测试书目：《被讨厌的勇气》

- 成片：1080×1920 竖屏，H.264 + AAC
- 时长：38.9 秒
- 大小：4.9 MB
- 耗时：约 90 秒（出图 60s + 语音 10s + 渲染 20s）

## 五步流水线

| 步骤 | 技术 | 产出 |
|---|---|---|
| 1. 文案 | 内置文案库 / ARK 文本模型 | 10 句文案 JSON（中文 + 英文 + 画面 prompt） |
| 2. 配图 | 豆包 doubao-seedream-5-0 | 10 张 2048×2048 AI 配图 |
| 3. 语音 | edge-tts（微软免费 TTS） | 10 段 mp3 + 精确时长 |
| 4. 渲染 | FFmpeg drawtext + Ken Burns | 10 个带字幕+镜头移动的视频片段 |
| 5. 合并 | FFmpeg concat | 1 条完整竖屏视频 |

## 快速开始

### 依赖

- Python 3.8+
- FFmpeg + ffprobe（系统 PATH）
- 火山 ARK API Key（用于豆包文生图）

### 安装

```bash
pip install edge-tts requests
```

### 运行

```bash
# 基本用法
python scripts/generate.py --book "被讨厌的勇气" --style cinematic --sentences 10

# 换风格
python scripts/generate.py --book "穷爸爸富爸爸" --style watercolor

# 换女声
python scripts/generate.py --book "原子习惯" --voice zh-CN-XiaoxiaoNeural
```

### 参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--book` | 必填 | 书名（中文） |
| `--style` | cinematic | 画面风格：cinematic / minimalist / watercolor / cyberpunk / vintage |
| `--voice` | zh-CN-YunxiNeural | edge-tts 语音 |
| `--sentences` | 10 | 文案句数（8-20） |
| `--output` | output/ | 产出目录 |
| `--skip-images` | false | 跳过出图，复用已有图片 |
| `--skip-gen-script` | false | 跳过文案生成，复用已有 JSON |

### 环境变量

```bash
export ARK_API_KEY="your-api-key-here"
```

或在 `~/.baoyu-skills/.env` 中配置：

```
ARK_API_KEY=your-api-key-here
```

## 内置文案库

| 书名 | 句数 | 核心主题 |
|---|---|---|
| 被讨厌的勇气 | 10 | 课题分离 / 被讨厌的勇气 / 此刻力量 |
| 穷爸爸富爸爸 | 10 | 资产vs负债 / 被动收入 / 财商 |
| 原子习惯 | 10 | 1%复利 / 四步循环 / 系统设计 |

其他书籍会尝试 ARK 文本模型，或降级为通用模板。

## 产出结构

```
output/
├── {book}_final.mp4          # 最终成片
├── {book}/
│   ├── segments/             # 各句视频片段
│   ├── images/               # AI 生成的配图
│   ├── voices/               # 逐句语音 mp3
│   └── {book}_script.json    # 文案数据（可复用/编辑）
```

## 支持的语音

| 语音名称 | 性别 | 风格 |
|---|---|---|
| zh-CN-YunxiNeural | 男 | 自然亲和 |
| zh-CN-XiaoxiaoNeural | 女 | 温暖明亮 |
| zh-CN-YunjianNeural | 男 | 深沉有力 |
| zh-CN-YunyangNeural | 男 | 专业播音 |

## 技术细节

### Ken Burns 镜头移动

4 个方向交替变换（右→左→下→上），用 FFmpeg 的 `scale` + `crop` 滤镜实现，比静止画面更生动。

### 字幕渲染

- 中文：微软雅黑粗体 52px，白色 + 黑色阴影 + 黑色描边
- 英文：Arial 32px，白色半透明 + 黑色阴影

### 出图模型

使用豆包 doubao-seedream-5-0-260128，比 4.0 版本画面质量和 prompt 理解能力更强。最小尺寸 2048×2048，后续由 FFmpeg 裁切到 1080×1920 竖屏。

## License

MIT
