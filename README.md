# 文件整理助手 organize.py

一个安全的命令行文件整理工具：指定一个文件夹，按文件类型自动归类到子文件夹。
**先预览、后执行、可撤销** —— 绝不覆盖你的任何文件。

## 为什么用这个工具？

- 🔒 **安全第一**：默认只预览，加 `--apply` 才真正移动
- ♻️ **可撤销**：每次整理都有历史记录，`--undo` 一键还原
- 🛡️ **绝不覆盖**：重名文件自动加序号（`photo.png` → `photo_1.png`）
- 🧹 **智能跳过**：不碰隐藏文件、子文件夹、程序自身
- 🪶 **零依赖**：纯 Python 标准库，装好 Python 就能用

## 安装

```bash
# 克隆仓库
git clone https://github.com/<你的用户名>/file-organizer.git
cd file-organizer
```

## 用法

```bash
# 预览：看看会整理哪些文件（不会移动任何东西）
python3 organize.py ~/Downloads

# 执行整理
python3 organize.py ~/Downloads --apply

# 撤销最近一次整理
python3 organize.py ~/Downloads --undo

# 查看帮助
python3 organize.py --help
```

### 示例

```bash
$ python3 organize.py ~/Downloads --apply

目标目录：/home/you/Downloads
模式：执行整理

以下 5 个文件将被移动：
  photo.jpg                      -> Images/photo.jpg
  report.pdf                     -> Documents/report.pdf
  movie.mp4                      -> Videos/movie.mp4
  song.mp3                       -> Audio/song.mp3
  backup.zip                     -> Archives/backup.zip

共 5 个文件：Archives(1), Audio(1), Documents(1), Images(1), Videos(1)

已移动 5/5 个文件。
历史记录：/home/you/Downloads/.organize_history.json（可用 --undo 撤销）
```

## 分类规则

| 类别 | 扩展名 |
| --- | --- |
| Images | jpg, jpeg, png, gif, webp, bmp, svg, ico, heic, raw |
| Documents | pdf, doc, docx, xls, xlsx, ppt, pptx, txt, md, csv, json, xml, epub |
| Videos | mp4, mov, avi, mkv, wmv, flv, webm, m4v |
| Audio | mp3, wav, flac, aac, ogg, m4a, wma |
| Archives | zip, rar, 7z, tar, gz, bz2, xz |
| Code | py, js, ts, java, c, cpp, h, go, rs, html, css, sh, sql |
| Others | 以上未匹配的任何文件 |

## 运行测试

```bash
python3 test_organize.py
```

## 项目结构

```
file-organizer/
├── organize.py        # 主程序
├── test_organize.py   # 自动化测试（8 个场景）
└── requirements.md    # 需求文档（v1 冻结）
```

## 路线图

- [ ] v2：自定义分类规则（JSON 配置文件）
- [ ] v2：按日期归类（`2026/08/` 文件夹）
- [ ] v2：清理空文件夹选项

## 许可证

MIT License —— 详见 [LICENSE](LICENSE)
