# 音频与播放器

路径相对于 SKILL_ROOT。使用脚本前先看 `--help`，替换下文 `{SKILL_ROOT}` 为实际安装位置。

## 准备与复用

先检查 MP3、manifest、字幕和时间戳。仅来源/范围一致、音频可解码且时长匹配才复用。
正文小修不重下，一分钟练习不先下载整期节目。脚本限制获取范围并有超时，不绕过访问限制。

```text
python3 "{SKILL_ROOT}/scripts/prepare_listening_audio.py" --help
python3 "{SKILL_ROOT}/scripts/prepare_listening_audio.py" --input-file "<本地媒体>" --start 0:00 --end 1:00 --output "<输出目录>/lesson-audio.mp3"
```

公开直链将 `--input-file` 换为 `--audio-url`；YouTube 使用 `--youtube-url`。仅选一个来源。
已有文件不匹配时不得直接覆盖，另存或先征得同意。用 ffprobe 核实时长并确认可解码。
ffmpeg 必须非交互运行、显式传递覆盖选项。

若来源受限，可用同一节目的合法公开音源或用户文件；换源核对开头、中间、结尾及偏移。
字幕候选可运行 `scripts/fetch_transcript.py --help`，仅提取练习区间；争议词仍须核对音频。

## 句子时间

优先复用带时间字幕并听音核对边界。缺少时间戳时才用本地 whisper.cpp：

```text
whisper-cli -f "<输出目录>/lesson-audio.mp3" -ojf -ml 1 -sow
```

参数以本机版本为准，模型路径按安装情况指定。将已确认原文写成 JSON：

```json
{"paragraphs": [["First sentence.", "Second sentence."], ["Another paragraph."]]}
```

```text
python3 "{SKILL_ROOT}/scripts/align_sentence_timestamps.py" --whisper-json "<词级JSON>" --sentences-json "<确认句子JSON>" --output "<输出目录>/timings.json"
```

覆盖率低、句数不一致、区间错位就回到音频复核，不硬凑时间。时间以裁切 MP3 的 0 秒为起点。
句尾覆盖末词全长，下一句包含首词；不能把末词起点当句尾，或漏掉 What/Yeah 等首词。

## 接入 HTML

先读模板。正文使用 `section.text > p`，每段译文用 `div.cn`。复制播放器到同目录。
模板中的本地 audio 默认 controls/preload；配置和播放器脚本必须在所有正文之后。

替换 `__INSERT_SAFE_LOCAL_AUDIO_FILENAME__` 为同目录 MP3 文件名：不含路径分隔符、冒号、查询或片段，
先做 HTML 属性编码，保留 src 的 `./` 前缀，不允许输入 HTML 或远程 URL。
替换 `__INSERT_PLAYER_CONFIG_JSON__` 为序列化配置，只有固定选择器和校验过的数字数组，不拼接任意 JS：

```json
{"audioSelector":"#practiceAudio","paragraphTimings":[[0,18.2]],"sentenceTimings":[[[0,4.1],[4.1,18.2]]],"sectionParagraphIndexes":[[0]]}
```

段落/句子/Section 索引必须对应正文顺序。脚本更新时更新 src 的版本查询参数防缓存。
分句检查和播放器一致：忽略 s/del 错误文本，将排版换行归一为同长度空格，避免 em/s 周围产生伪句子。

## 不得回退的交互规则

1. 主按钮连续“播放/暂停”，保留当前位置且可跨节；整段结束才显示“从头播放”。
2. 点正文句子、句子节点或“重听本句”，才回句首播放并在句末暂停。
3. “播放本节”从节首到节末；节末暂停后主键继续下一节。
4. 空格是页面级快捷键，普通按钮/词卡/弹窗有焦点也生效且不滚屏；仅文字输入/可编辑元素、
   倍速下拉框、进度滑块等需要原生键盘操作的控件例外。按住空格不重复触发。
5. 轻点轨道定位并立刻播放；拖动保持拖动前的播放/暂停状态，并退出旧 stopAt 范围。
6. 节点与滑块共用时间配置及有效行程。固定滑块直径，标记轨道左右各缩进半个直径，清除按钮 padding。
   圆心与可见轨道垂直中心重合，不能对齐到 range 外框顶部。无法验证定位时隐藏节点。
7. 每节“查看原文/返回批改”只影响本节。原文态隐藏 s/del，em/ins 普通显示，保留 tip 和句子点击，不重排文本。
8. 创建按钮时直接给文案，初始化即显示单一底部播放器，不等 play/timeupdate 才显示入口。
   初始化成功才隐藏原生控件，失败须可见提示。

## 验收

按“文件可解码 → 首屏入口 → 点击/媒体状态 → 句子定位”顺序检查；入口故障不代表要重新下载。

- MP3 同目录且时长正确，默认 controls/preload，无远程播放依赖。
- 每节初次打开已有播放文字，底部播放器可见。
- 实际点击后 duration 合理、currentTime 持续增加、audio.error 为空；句末自动暂停。
- 句子高亮及暂停/结束状态正确；核对首/中/末句与争议边界。
- 验证四路径：句中暂停→主键继续；单句结束→主键/空格继续后文；节末暂停→主键进入下一节；重听本句→句首。
- 空格不滚页、不触发焦点按钮的第二次点击，输入/下拉框仍正常；轻点轨道即播放，拖动保持状态。
- 五档倍速 0.5、0.75、1、1.25、1.5 可用；宽窄屏节点与滑块及轨道中心重合。
- 切换一节原文不改变其他节，词卡和句子点击不受影响。
- 语法/模拟测试不能代替真实媒体播放，未测或失败必须说明。

首次交付做一次完整验收。正文小改仅测受影响部分；共享播放器修改再做核心交互回归。
