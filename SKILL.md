---
title: "拆书成视频 Skill"
summary: "给一本书名，自动生成一条 9:16 竖屏书单短视频（AI 配图 + 语音朗读 + 中英字幕 + Ken Burns 镜头移动）"
read_when:
  - 用户想把一本书做成短视频
  - 用户提到"书单视频""拆书成视频""book video"
  - 用户需要批量生成书单号内容
---

# 拆书成视频 Skill

## 一句话

给一本书名，出一条 9:16 竖屏短视频。AI 写文案、豆包出图、edge-tts 朗读、FFmpeg 渲染字幕和镜头移动，全自动。

## 依赖

- Python 3.8+
- FFmpeg + ffprobe（系统 PATH）
- edge-tts（`pip install edge-tts`）
- requests（`pip install requests`）
- 火山 ARK API Key（环境变量 `ARK_API_KEY`，或从 `~/.baoyu-skills/.env` 自动读取）
- Windows 字体：`C:/Windows/Fonts/msyhbd.ttc`（中文粗体）、`C:/Windows/Fonts/arial.ttf`（英文）

## 用法

```bash
# 基本用法（推荐）
python scripts/generate.py --book "被讨厌的勇气" --style cinematic --voice zh-CN-YunxiNeural --sentences 10 --output output/

# 跳过出图（复用已生成的图片）
python scripts/generate.py --book "被讨厌的勇气" --skip-images --skip-gen-script --output output/
```

### 参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--book` | 必填 | 书名（中文） |
| `--style` | cinematic | 画面风格前缀：cinematic / minimalist / watercolor / cyberpunk / vintage |
| `--voice` | zh-CN-YunxiNeural | edge-tts 语音：YunxiNeural（男）/ XiaoxiaoNeural（女）/ YunjianNeural（男深沉） |
| `--sentences` | 10 | 文案句数（8-20） |
| `--output` | output/ | 产出目录 |
| `--skip-gen-script` | false | 跳过文案生成，用已有的 JSON |
| `--skip-images` | false | 跳过出图，用已有图片 |

## 产出

```
output/
├── {book}_final.mp4          ← 最终成片（1080×1920 H.264 + AAC）
├── {book}/
│   ├── segments/             ← 各句视频片段
│   ├── images/               ← AI 生成的配图（2048×2048）
│   ├── voices/               ← 逐句语音 mp3
│   └── {book}_script.json    ← 文案数据（可复用/编辑）
```

## 流水线五步

1. **文案生成**：内置 3 本书文案库（被讨厌的勇气 / 穷爸爸富爸爸 / 原子习惯），未命中时尝试 ARK 文本模型，兜底用通用模板
2. **豆包出图**：每句英文 prompt 发给 doubao-seedream-5-0，生成 2048×2048 图片
3. **语音合成**：edge-tts 逐句生成 mp3，ffprobe 获取精确时长
4. **渲染片段**：FFmpeg scale+crop（Ken Burns 镜头移动）+ drawtext（中英字幕）+ 语音，输出单句片段
5. **合并**：FFmpeg concat 拼接所有片段，叠加完整音轨，输出 1080×1920 mp4

## 内置文案库

| 书名 | 句数 | 核心主题 |
|---|---|---|
| 被讨厌的勇气 | 10 | 课题分离 / 被讨厌的勇气 / 此刻力量 |
| 穷爸爸富爸爸 | 10 | 资产vs负债 / 被动收入 / 财商 |
| 原子习惯 | 10 | 1%复利 / 四步循环 / 系统设计 |

其他书籍会尝试 ARK 文本模型（需正确的模型 ID），或降级为通用模板。

## 故障排查

- **出图失败**：检查 ARK_API_KEY 是否有效，网络是否通 ark.cn-beijing.volces.com
- **语音失败**：edge-tts 偶尔断连，脚本会重试 3 次
- **字幕乱码**：确认字体路径 C:/Windows/Fonts/msyhbd.ttc 存在
- **渲染报错**：检查 FFmpeg 版本 ≥ 6.0，drawtext 需要 libfreetype 支持
- **画面风格跳**：同一本书用同一个 `--style` 参数，保证全局风格一致

## 实测数据（2026-07-25）

- 测试书目：《被讨厌的勇气》
- 10 句文案 → 10 张 AI 配图 → 10 段语音 → 10 个片段 → 1 条成片
- 成片：1080×1920，H.264，38.9 秒，4.9MB
- 总耗时：约 90 秒（出图 60s + 语音 10s + 渲染 20s）
