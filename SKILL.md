---
name: book-video-maker
version: "1.1.0"
summary: "给一本书名，自动生成一条 9:16 竖屏书单短视频（AI 配图 + 语音朗读 + 中英字幕 + Ken Burns 镜头移动）"
read_when:
  - 用户想把一本书做成短视频
  - 用户提到"书单视频""拆书成视频""book video""书单号"
  - 用户需要批量生成书单号内容
  - 用户想用 AI 自动生成竖屏视频
  - 用户提到"豆包出图""edge-tts""FFmpeg 视频渲染"
---

# 拆书成视频 Skill

## 一句话

给一本书名，出一条 9:16 竖屏短视频。AI 写文案、豆包出图、edge-tts 朗读、FFmpeg 渲染字幕和镜头移动，全自动。

## 依赖

- Python 3.8+
- FFmpeg + ffprobe（系统 PATH，版本 ≥ 6.0，需 libfreetype 支持 drawtext）
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
| `--style` | cinematic | 画面风格：cinematic / minimalist / watercolor / cyberpunk / vintage |
| `--voice` | zh-CN-YunxiNeural | edge-tts 语音：YunxiNeural（男）/ XiaoxiaoNeural（女）/ YunjianNeural（男深沉）/ YunyangNeural（专业播音） |
| `--sentences` | 10 | 文案句数（8-20） |
| `--output` | output/ | 产出目录 |
| `--skip-images` | false | 跳过出图，复用已有图片 |
| `--skip-gen-script` | false | 跳过文案生成，复用已有 JSON |

## 产出

```
output/
├── {book}_final.mp4          ← 最终成片（1080×1920 H.264 + AAC）
├── {book}/
│   ├── segments/             ← 各句视频片段
│   ├── images/               ← AI 生成的配图（优先 9:16，降级 1:1）
│   ├── voices/               ← 逐句语音 mp3
│   └── {book}_script.json    ← 文案数据（可复用/编辑）
```

## 流水线五步

| 步骤 | 输入 | 处理 | 输出 |
|---|---|---|---|
| 1. 文案 | 书名 + 句数 + 风格 | 内置文案库 → ARK 文本模型 → 通用模板（三级降级） | JSON 数组（cn/en/prompt 三字段） |
| 2. 配图 | 英文 prompt + 风格前缀 | 豆包 API 优先 9:16（1440×2560），降级 1:1（2048×2048）+ 竖屏构图提示 | 10 张 JPG |
| 3. 语音 | 中文文案 + voice 参数 | edge-tts 逐句合成，ffprobe 取精确时长 | 10 段 mp3 + 时长列表 |
| 4. 渲染 | 图片 + 语音 + 中英文案 | FFmpeg scale+crop（Ken Burns）+ drawtext（字幕）+ 语音 | 10 个 mp4 片段 |
| 5. 合并 | 10 个片段 + 10 段语音 | FFmpeg concat 拼接视频 + concat 拼接音频 → 合流 | 1 条 1080×1920 mp4 |

## 失败模式与处理（if-then 三段式）

| 触发条件 | 一线修复 | 仍失败兜底 |
|---|---|---|
| ARK 文本模型 404 / 权限不足 | 切换到下一个模型 ID 尝试 | 降级到内置文案库或通用模板 |
| 豆包出图返回 "size must be at least 3686400" | 尝试更大的 9:16 尺寸（1620×2880） | 降级到 2048×2048 + 竖屏构图提示 |
| 豆包出图连续 3 次失败 | 检查 ARK_API_KEY 是否有效 | 生成纯色 1440×2560 占位图，流程不中断 |
| edge-tts 断连 | 重试 3 次，间隔 2 秒 | 该句时长设为 3.0 秒，语音留空 |
| FFmpeg drawtext 报 "No option name near" | 字体路径 `C:` 转义为 `C\:` | 确认字体文件存在于 `C:/Windows/Fonts/` |
| FFmpeg drawtext 报 "Error parsing filterchain" | 英文撇号 `'` 替换为 unicode `\u2019` | 检查文案是否含 `:` `%` `\` 并转义 |
| FFmpeg crop 报 "Invalid argument" | 检查 Ken Burns 表达式括号是否匹配 | 简化表达式去掉 if 判断 |
| 合并时视频/音频时长不一致 | `-shortest` 参数截断 | 以视频时长为准，丢弃多余音频 |
| 字幕乱码或方块 | 确认 msyhbd.ttc 存在且 fontfile 路径正确 | 安装微软雅黑字体或替换为 simhei.ttf |

## 🛑 STOP · 启动前检查点

运行前必须全部通过，否则脚本会退出：

| # | 检查项 | 不通过时处理 |
|---|---|---|
| 1 | `ARK_API_KEY` 非空或 `~/.baoyu-skills/.env` 存在 | 手动配置环境变量 |
| 2 | `ffmpeg -version` 返回 0 | 安装 FFmpeg ≥ 6.0 并加入 PATH |
| 3 | `ffprobe -version` 返回 0 | 同上（FFmpeg 自带） |
| 4 | `C:/Windows/Fonts/msyhbd.ttc` 存在 | 安装微软雅黑粗体 |
| 5 | `C:/Windows/Fonts/arial.ttf` 存在 | 安装 Arial 字体 |
| 6 | `import edge_tts` 成功 | `pip install edge-tts` |

## 🔴 运行中检查点

| 步骤 | 检查内容 | 失败时降级 |
|---|---|---|
| Step 2 出图后 | 每张图 > 0 字节 | 纯色 1440×2560 占位图 |
| Step 3 语音后 | 每段 mp3 > 100 字节 | 时长设 3.0 秒，语音留空 |
| Step 4 渲染后 | 每个片段 returncode == 0 | 打印 stderr 最后 200 字符，终止流程 |

## 反例黑名单（不要做）

| # | 反模式 | 为什么不要做 | 替代做法 |
|---|---|---|---|
| 1 | `scale=1188:2112` 不加 `force_original_aspect_ratio` | 1:1 图被拉伸变形，人脸变长 | 必须加 `:force_original_aspect_ratio=increase` |
| 2 | 直接请求 1080×1920 出图 | 像素数 2073600 < 豆包最低 3686400 | 用 1440×2560 或 2048×2048 |
| 3 | drawtext 的 `fontfile` 路径含 `C:` 不转义 | 冒号被当作选项分隔符 | `C\:/Windows/Fonts/...` |
| 4 | drawtext 文案含英文撇号 `'` | 破坏 FFmpeg 单引号字符串 | 替换为 `\u2019`（unicode 右单引号） |
| 5 | Ken Burns 表达式多余括号 | FFmpeg 报错位置不准，难定位 | 简化表达式，去掉嵌套 if |
| 6 | Ken Burns 非移动轴不居中 | 裁切区域偏在角落，画面构图差 | 固定 `'(MAX_Y/2)'` 或 `'(MAX_X/2)'` |
| 7 | 用 PIL 生成示意图当"截图" | 违反工具测评门槛（需真实截图） | 用 FFmpeg 提取真实帧或截屏 |
| 8 | 混用不同 `--style` 生成同一本书 | 画面风格跳变 | 全书用同一 `--style` |

## 内置文案库

| 书名 | 句数 | 核心主题 |
|---|---|---|
| 被讨厌的勇气 | 10 | 课题分离 / 被讨厌的勇气 / 此刻力量 |
| 穷爸爸富爸爸 | 10 | 资产vs负债 / 被动收入 / 财商 |
| 原子习惯 | 10 | 1%复利 / 四步循环 / 系统设计 |

其他书籍会尝试 ARK 文本模型，或降级为通用模板。

## 技术细节

### 出图尺寸策略

| 优先级 | 尺寸 | 比例 | 像素数 | 说明 |
|---|---|---|---|---|
| 1 | 1440×2560 | 9:16 | 3,686,400 | 精确 9:16，豆包最低线 |
| 2 | 1620×2880 | 9:16 | 4,665,600 | 安全余量 |
| 3（降级） | 2048×2048 | 1:1 | 4,194,304 | 加竖屏构图提示 |

### Ken Burns 镜头移动

两阶段裁切（无变形）：
1. `scale=1188:2112:force_original_aspect_ratio=increase` — 无 distortion 缩放
2. `crop=1188:2112:'(iw-1188)/2':'(ih-2112)/2'` — 居中裁切到统一尺寸
3. `crop=1080:1920:X:Y` — Ken Burns 移动裁切

4 个方向交替（右→左→下→上），非移动轴居中。

### 字幕渲染

- 中文：微软雅黑粗体 52px，白色 + 黑色阴影 + 黑色描边
- 英文：Arial 32px，白色半透明 + 黑色阴影
- 位置：画面 72% 高度处居中

## 实测数据（2026-07-25）

- 测试书目：《被讨厌的勇气》
- 10 句文案 → 10 张 AI 配图 → 10 段语音 → 10 个片段 → 1 条成片
- 成片：1080×1920，H.264，38.9 秒，4.9MB
- 总耗时：约 90 秒（出图 60s + 语音 10s + 渲染 20s）

## License

MIT
