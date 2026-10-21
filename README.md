# my-skills

我自己写、日常在用的 Agent Skills，适用于 Claude Code / Codex 等支持 `SKILL.md` 的 agent。

| Skill | 用途 |
|---|---|
| [paper-cn](skills/paper-cn) | 把英文论文（arXiv 优先）翻成中文精读稿：术语保留英文、歧义处挂脚注附原文、每章末附译者小结，并抽取论文插图 |
| [scout](skills/scout) | 从模糊想法 / JD / 能力缺口出发扩展关键词，在 GitHub、HuggingFace、arXiv 检索值得学习的开源项目和资源 |
| [english-dictation-coach](skills/english-dictation-coach) | 英语精听批改：拉取视频字幕，对比手写听写，生成可逐句回听的 HTML 红笔批改页 |

## 安装

把需要的 skill 目录复制（或软链接）到 agent 的 skills 目录：

```bash
git clone https://github.com/Xiaxia1997/my-skills.git
cp -r my-skills/skills/paper-cn ~/.claude/skills/
```

## 依赖

- **paper-cn**：Python 3 + `lxml`；抽图需要 poppler（`pdftotext` / `pdftoppm` / `pdfinfo`）
- **english-dictation-coach**：见该目录下的 `SKILL.md`
- **scout**：无额外依赖，需要 agent 能联网搜索

## License

MIT
