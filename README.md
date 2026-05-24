# 🎨 Pinterest 高清图片爬取工具

> 专为 Facebook 公共主页配图灵感收集而设计的分层爬取工具

[![Build and Release](https://github.com/YOUR_USERNAME/FindPosts/actions/workflows/build-release.yml/badge.svg)](https://github.com/YOUR_USERNAME/FindPosts/actions/workflows/build-release.yml)
[![CodeQL](https://github.com/YOUR_USERNAME/FindPosts/actions/workflows/codeql.yml/badge.svg)](https://github.com/YOUR_USERNAME/FindPosts/actions/workflows/codeql.yml)

## ✨ 功能特点

- 🔍 **双模式爬取** — 支持关键词搜索和直接 Pinterest 链接输入
- 🌳 **分层爬取** — 从主图出发，自动抓取"More like this"延伸图片
- 📸 **高清画质** — 自动升级为 originals/736x 高清原图链接
- 🗂️ **智能分类** — 按批次、任务、层级自动创建分类文件夹
- 🛡️ **防风控** — 随机休眠、模拟人类滚动、隐藏自动化特征
- ♻️ **容错机制** — 自动跳过死链，不因单张失败导致程序崩溃
- 🖥️ **现代 UI** — 深色主题 GUI，实时日志，进度反馈

## 📁 目录结构

```
图片保存根目录/
├── 2025-05-24_143022/          # 批次目录（日期+时间戳）
│   ├── 美食摄影/               # 任务目录（关键词命名）
│   │   ├── 第一层-最相关/      # 搜索结果主图
│   │   └── 延申-扩展/          # 相关延伸图片
│   └── Pin_123456789/          # 任务目录（Pin ID 命名）
│       ├── 第一层-最相关/      # 原始 Pin 图片
│       └── 延申-扩展/          # 延伸相关图片
└── _logs/                       # 运行日志
```

## 🚀 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行程序

```bash
python app.py
```

### 使用方法

1. **设置保存路径** — 点击「浏览」选择图片储存目录
2. **输入任务** — 每行一个关键词或 Pinterest 链接：
   - 关键词：`美食摄影`、`minimalist home decor`
   - 链接：`https://www.pinterest.com/pin/123456789/`
3. **调整参数** — 设置每层图片数量和爬取层级
4. **开始爬取** — 点击「🚀 开始爬取」

## ⚙️ 参数说明

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| 每层图片数量 | 每个层级抓取的图片数 | 10-20 |
| 爬取层级 | 向下深挖的层数 | 2-3 |

## 🔧 技术栈

- **Python 3.8+**
- **Selenium 4** — 无头 Chrome 浏览器自动化
- **WebDriver Manager** — 自动管理 ChromeDriver 版本
- **Requests** — 高效图片下载
- **Tkinter** — 原生跨平台 GUI

## 📋 系统要求

- Windows 10/11（或 macOS/Linux）
- Python 3.8 或更高版本
- Google Chrome 浏览器（已安装）
- 网络连接（能访问 Pinterest）

## ⚠️ 注意事项

- 本工具仅供个人学习和灵感收集使用
- 请遵守 Pinterest 服务条款
- 建议不要设置过高的爬取频率，避免 IP 被封禁
- 下载的图片版权归原作者所有

## 📝 License

MIT License
