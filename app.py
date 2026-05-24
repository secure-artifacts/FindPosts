"""
Pinterest Image Crawler - UI 主界面
现代化深色主题 Tkinter GUI
v1.0.0
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from datetime import datetime
from pathlib import Path

try:
    import pystray
    from pystray import MenuItem as TrayItem
    from PIL import Image as PILImage
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

# 确保能导入爬虫模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pinterest_crawler import PinterestCrawler, setup_logger


def resource_path(relative_path: str) -> str:
    """获取资源文件的绝对路径（兼容 PyInstaller 打包后的路径）"""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包后，资源解压到临时目录 _MEIPASS
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


# ─────────────────────────────────────────────
# 颜色主题
# ─────────────────────────────────────────────
THEME = {
    "bg_dark": "#0F0F1A",        # 最深背景
    "bg_panel": "#16162A",       # 面板背景
    "bg_card": "#1E1E35",        # 卡片背景
    "bg_input": "#252540",       # 输入框背景
    "bg_hover": "#2A2A4A",       # 悬停背景
    "accent": "#E60023",         # Pinterest 红
    "accent_dark": "#B8001C",    # 深红
    "accent_glow": "#FF1744",    # 发光红
    "purple": "#7C4DFF",         # 紫色点缀
    "cyan": "#00BCD4",           # 青色
    "green": "#00E676",          # 成功绿
    "yellow": "#FFD740",         # 警告黄
    "text_primary": "#F5F5F5",   # 主文字
    "text_secondary": "#9E9EBE", # 次要文字
    "text_muted": "#5A5A7A",     # 灰色文字
    "border": "#2D2D4D",         # 边框
    "border_focus": "#E60023",   # 焦点边框
    "shadow": "#090914",         # 阴影
}


# ─────────────────────────────────────────────
# 自定义 Widget
# ─────────────────────────────────────────────
class ModernButton(tk.Button):
    """现代化按钮"""
    
    def __init__(self, parent, text, command=None, style="primary", **kwargs):
        colors = {
            "primary": (THEME["accent"], THEME["accent_dark"], THEME["text_primary"]),
            "secondary": (THEME["bg_card"], THEME["bg_hover"], THEME["text_secondary"]),
            "success": ("#00897B", "#006B5E", THEME["text_primary"]),
            "danger": (THEME["accent"], THEME["accent_dark"], THEME["text_primary"]),
            "purple": (THEME["purple"], "#6035E0", THEME["text_primary"]),
        }
        
        bg, active_bg, fg = colors.get(style, colors["primary"])
        
        # 允许调用方通过 kwargs 覆盖默认的 padx/pady/font
        padx = kwargs.pop("padx", 20)
        pady = kwargs.pop("pady", 10)
        font = kwargs.pop("font", ("Segoe UI", 10, "bold"))
        
        super().__init__(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active_bg,
            activeforeground=fg,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
            padx=20,
            pady=10,
            **kwargs
        )
        
        self._bg = bg
        self._active_bg = active_bg
        self.bind("<Enter>", lambda e: self.config(bg=active_bg))
        self.bind("<Leave>", lambda e: self.config(bg=self._bg))


class ModernSlider(tk.Frame):
    """Canvas 自绘现代滑块 — 高对比度、可视性强"""

    TRACK_H = 8    # 轨道高度 px
    THUMB_R = 11   # 滑块圆半径 px
    PAD    = 14    # 左右边距

    def __init__(self, parent, variable, from_=0, to=100, resolution=1, **kwargs):
        super().__init__(parent, bg=THEME["bg_card"], **kwargs)
        self._var       = variable
        self._from      = from_
        self._to        = to
        self._res       = resolution
        self._dragging  = False

        self._canvas = tk.Canvas(
            self,
            height=self.THUMB_R * 2 + 8,
            bg=THEME["bg_card"],
            highlightthickness=0,
            cursor="hand2",
        )
        self._canvas.pack(fill="x", expand=True, pady=4)

        self._canvas.bind("<Configure>",      lambda e: self._redraw())
        self._canvas.bind("<ButtonPress-1>",  self._on_press)
        self._canvas.bind("<B1-Motion>",      self._on_drag)
        self._canvas.bind("<ButtonRelease-1>",self._on_release)
        self._var.trace_add("write",          lambda *_: self._redraw())

    # 将数局转成 canvas x 坐标
    def _val_to_x(self, val, w):
        frac = (val - self._from) / max(self._to - self._from, 1)
        return self.PAD + frac * (w - self.PAD * 2)

    # 将 canvas x 转成数局，并 snap 到 resolution
    def _x_to_val(self, x, w):
        frac = (x - self.PAD) / max(w - self.PAD * 2, 1)
        frac = max(0.0, min(1.0, frac))
        raw  = self._from + frac * (self._to - self._from)
        snapped = round(raw / self._res) * self._res
        return int(max(self._from, min(self._to, snapped)))

    def _redraw(self):
        c = self._canvas
        c.delete("all")
        w = c.winfo_width()
        if w < 2:
            return
        h  = c.winfo_height()
        cy = h // 2
        tr = self.TRACK_H // 2
        val = self._var.get()
        tx  = self._val_to_x(val, w)

        # 轨道底色（深色背景）
        c.create_rectangle(
            self.PAD, cy - tr, w - self.PAD, cy + tr,
            fill="#0A0A18", outline=THEME["border"], width=1,
        )
        # 已填充部分（酷红渐变）
        if tx > self.PAD:
            c.create_rectangle(
                self.PAD, cy - tr, tx, cy + tr,
                fill=THEME["accent"], outline="",
            )
        # 滑块阴影（用 stipple 模拟半透明，Tkinter 不支持 8 位 hex alpha）
        r = self.THUMB_R
        c.create_oval(
            tx - r + 2, cy - r + 2, tx + r + 2, cy + r + 2,
            fill="#0A0A18", outline="", stipple="gray25",
        )
        # 滑块本体（白色 + 红色边框）
        c.create_oval(
            tx - r, cy - r, tx + r, cy + r,
            fill="#FFFFFF", outline=THEME["accent"], width=2,
        )

    def _on_press(self, e):
        self._dragging = True
        self._set_from_x(e.x)

    def _on_drag(self, e):
        if self._dragging:
            self._set_from_x(e.x)

    def _on_release(self, e):
        self._dragging = False

    def _set_from_x(self, x):
        w = self._canvas.winfo_width()
        self._var.set(self._x_to_val(x, w))


class ModernEntry(tk.Entry):
    """现代化输入框"""
    
    def __init__(self, parent, placeholder="", **kwargs):
        super().__init__(
            parent,
            bg=THEME["bg_input"],
            fg=THEME["text_primary"],
            insertbackground=THEME["accent"],
            relief="flat",
            bd=0,
            font=("Segoe UI", 10),
            **kwargs
        )
        self._placeholder = placeholder
        self._has_placeholder = False
        
        if placeholder:
            self._show_placeholder()
            self.bind("<FocusIn>", self._on_focus_in)
            self.bind("<FocusOut>", self._on_focus_out)
    
    def _show_placeholder(self):
        self.insert(0, self._placeholder)
        self.config(fg=THEME["text_muted"])
        self._has_placeholder = True
    
    def _on_focus_in(self, event):
        if self._has_placeholder:
            self.delete(0, tk.END)
            self.config(fg=THEME["text_primary"])
            self._has_placeholder = False
    
    def _on_focus_out(self, event):
        if not self.get():
            self._show_placeholder()
    
    def get_value(self) -> str:
        """获取真实值（忽略占位符）"""
        if self._has_placeholder:
            return ""
        return self.get()


class LogPanel(scrolledtext.ScrolledText):
    """日志面板"""
    
    LEVEL_COLORS = {
        "✅": "#00E676",   # 成功
        "❌": "#FF5252",   # 错误
        "⚠️": "#FFD740",   # 警告
        "🚀": "#7C4DFF",   # 启动
        "📥": "#00BCD4",   # 下载
        "📁": "#FF9800",   # 文件夹
        "🔎": "#E91E63",   # 搜索
        "🔗": "#9C27B0",   # 链接
        "🌿": "#4CAF50",   # 延伸
        "🎉": "#FFD740",   # 完成
        "📌": "#E60023",   # 任务
        "📸": "#00BCD4",   # 图片
        "⏳": "#78909C",   # 等待
        "⏹️": "#78909C",   # 停止
        "🔒": "#78909C",   # 关闭
        "=": "#2D2D4D",    # 分隔线
    }
    
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            bg=THEME["bg_dark"],
            fg=THEME["text_primary"],
            font=("Consolas", 9),
            relief="flat",
            bd=0,
            wrap=tk.WORD,
            state="disabled",
            selectbackground=THEME["bg_hover"],
            **kwargs
        )
        
        # 配置颜色标签
        for emoji, color in self.LEVEL_COLORS.items():
            self.tag_config(f"tag_{emoji}", foreground=color)
        self.tag_config("timestamp", foreground=THEME["text_muted"])
        self.tag_config("default", foreground=THEME["text_secondary"])
    
    def append(self, message: str):
        """追加日志消息"""
        self.config(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        self.insert(tk.END, f"[{timestamp}] ", "timestamp")
        
        # 根据消息内容选择颜色
        color_tag = "default"
        for emoji, _ in self.LEVEL_COLORS.items():
            if emoji in message:
                color_tag = f"tag_{emoji}"
                break
        
        self.insert(tk.END, message + "\n", color_tag)
        self.see(tk.END)
        self.config(state="disabled")
    
    def clear(self):
        """清空日志"""
        self.config(state="normal")
        self.delete(1.0, tk.END)
        self.config(state="disabled")


# ─────────────────────────────────────────────
# 主 UI 类
# ─────────────────────────────────────────────
class PinterestCrawlerApp:
    """Pinterest爬虫主界面"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Pinterest 高清图片爬取工具")
        self.root.geometry("1100x780")
        self.root.minsize(900, 650)
        self.root.configure(bg=THEME["bg_dark"])

        # ── 设置窗口图标（任务栏 + 标题栏）──
        self._icon_path = resource_path("log.ico")
        self._pil_icon = None
        self._tray_icon = None
        try:
            if os.path.exists(self._icon_path):
                self.root.iconbitmap(self._icon_path)
        except Exception:
            pass
        # 加载 PIL 图像，供系统托盘使用
        try:
            self._pil_icon = PILImage.open(self._icon_path)
        except Exception:
            self._pil_icon = None
        
        # 状态变量
        self.crawler: PinterestCrawlerApp = None
        self.crawler_thread: threading.Thread = None
        self.stop_event = threading.Event()
        self.is_running = False
        
        # 配置变量
        self.save_path_var = tk.StringVar(value=str(Path.home() / "Pictures" / "Pinterest爬取"))
        self.imgs_per_layer_var = tk.IntVar(value=10)
        self.max_layers_var = tk.IntVar(value=2)
        
        self._setup_styles()
        self._build_ui()
        self._center_window()
    
    def _setup_styles(self):
        """配置 ttk 样式"""
        style = ttk.Style()
        style.theme_use("clam")
        
        # Progressbar
        style.configure(
            "Pinterest.Horizontal.TProgressbar",
            troughcolor=THEME["bg_card"],
            background=THEME["accent"],
            lightcolor=THEME["accent"],
            darkcolor=THEME["accent_dark"],
            bordercolor=THEME["bg_card"],
            thickness=6,
        )
        
        # Scale
        style.configure(
            "Pinterest.Horizontal.TScale",
            background=THEME["bg_panel"],
            troughcolor=THEME["bg_card"],
        )
        
        # Separator
        style.configure(
            "Pinterest.TSeparator",
            background=THEME["border"]
        )
    
    def _center_window(self):
        """窗口居中"""
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")
    
    def _build_ui(self):
        """构建主界面"""
        # 顶部标题栏
        self._build_header()
        
        # 主内容区（左右布局）
        main_frame = tk.Frame(self.root, bg=THEME["bg_dark"])
        main_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        
        # 左侧配置区
        left_frame = tk.Frame(main_frame, bg=THEME["bg_dark"])
        left_frame.pack(side="left", fill="both", expand=False, padx=(0, 8))
        left_frame.config(width=380)
        left_frame.pack_propagate(False)
        
        self._build_config_panel(left_frame)
        
        # 右侧日志区
        right_frame = tk.Frame(main_frame, bg=THEME["bg_dark"])
        right_frame.pack(side="left", fill="both", expand=True)
        
        self._build_log_panel(right_frame)
        
        # 底部状态栏
        self._build_status_bar()
    
    def _build_header(self):
        """构建顶部标题栏"""
        header = tk.Frame(self.root, bg=THEME["bg_panel"], height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        # Pinterest Logo 风格
        logo_frame = tk.Frame(header, bg=THEME["bg_panel"])
        logo_frame.pack(side="left", padx=20, pady=12)
        
        # P 图标
        p_icon = tk.Label(
            logo_frame,
            text="P",
            font=("Georgia", 28, "bold"),
            bg=THEME["accent"],
            fg="white",
            width=2,
            relief="flat",
            bd=0,
        )
        p_icon.pack(side="left", ipady=2)
        
        # 标题文字
        title_frame = tk.Frame(logo_frame, bg=THEME["bg_panel"])
        title_frame.pack(side="left", padx=12)
        
        tk.Label(
            title_frame,
            text="Pinterest 高清图片爬取工具",
            font=("Segoe UI", 16, "bold"),
            bg=THEME["bg_panel"],
            fg=THEME["text_primary"],
        ).pack(anchor="w")
        
        tk.Label(
            title_frame,
            text="分层爬取 · 高清原图 · 自动分类",
            font=("Segoe UI", 9),
            bg=THEME["bg_panel"],
            fg=THEME["text_muted"],
        ).pack(anchor="w")
        
        # 右侧信息
        info_label = tk.Label(
            header,
            text="🎨 Facebook 配图灵感收集器",
            font=("Segoe UI", 10),
            bg=THEME["bg_panel"],
            fg=THEME["text_secondary"],
        )
        info_label.pack(side="right", padx=20)
        
        # 分隔线
        sep = tk.Frame(self.root, bg=THEME["accent"], height=2)
        sep.pack(fill="x")
    
    def _section_header(self, parent, text: str, icon: str = ""):
        """创建区块标题"""
        frame = tk.Frame(parent, bg=THEME["bg_card"])
        frame.pack(fill="x", padx=0, pady=(0, 2))
        
        tk.Label(
            frame,
            text=f"{icon} {text}" if icon else text,
            font=("Segoe UI", 11, "bold"),
            bg=THEME["bg_card"],
            fg=THEME["text_primary"],
        ).pack(side="left", padx=12, pady=8)
        
        return frame
    
    def _card(self, parent, **kwargs):
        """创建卡片容器"""
        card = tk.Frame(parent, bg=THEME["bg_card"], **kwargs)
        card.pack(fill="x", pady=4)
        return card
    
    def _label(self, parent, text, fg=None, font=None, **kwargs):
        """创建标签"""
        return tk.Label(
            parent,
            text=text,
            bg=THEME["bg_card"],
            fg=fg or THEME["text_secondary"],
            font=font or ("Segoe UI", 9),
            **kwargs
        )
    
    def _build_config_panel(self, parent):
        """构建左侧配置面板"""

        # ── 操作按钮（先占底部，永远可见）──
        btn_card = tk.Frame(parent, bg=THEME["bg_card"],
                            highlightthickness=2,
                            highlightbackground=THEME["accent"])
        btn_card.pack(side="bottom", fill="x", pady=(8, 0))

        btn_inner = tk.Frame(btn_card, bg=THEME["bg_card"])
        btn_inner.pack(fill="x", padx=12, pady=10)

        self.start_btn = ModernButton(
            btn_inner, "🚀  开始爬取", command=self._start_crawl,
            style="primary", padx=24, pady=10,
            font=("Segoe UI", 11, "bold"),
        )
        self.start_btn.pack(side="left", padx=(0, 8))

        self.stop_btn = ModernButton(
            btn_inner, "⏹ 停止", command=self._stop_crawl,
            style="secondary", padx=16, pady=10,
        )
        self.stop_btn.pack(side="left", padx=(0, 8))
        self.stop_btn.config(state="disabled")

        open_btn = ModernButton(
            btn_inner, "📂 打开目录", command=self._open_save_dir,
            style="purple", padx=16, pady=10,
        )
        open_btn.pack(side="right")

        # ── 储存路径 ──
        path_card = self._card(parent)
        self._section_header(path_card, "储存路径", "📁")
        
        path_inner = tk.Frame(path_card, bg=THEME["bg_card"])
        path_inner.pack(fill="x", padx=12, pady=(0, 12))
        
        path_row = tk.Frame(path_inner, bg=THEME["bg_card"])
        path_row.pack(fill="x")
        
        path_entry = tk.Entry(
            path_row,
            textvariable=self.save_path_var,
            bg=THEME["bg_input"],
            fg=THEME["text_primary"],
            insertbackground=THEME["accent"],
            relief="flat",
            bd=0,
            font=("Segoe UI", 9),
        )
        path_entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(2, 6))
        
        browse_btn = ModernButton(
            path_row, "浏览", command=self._browse_path,
            style="secondary", padx=12, pady=6
        )
        browse_btn.pack(side="right")
        
        # ── 关键词/链接输入 ──
        keyword_card = self._card(parent)
        self._section_header(keyword_card, "关键词 / Pinterest 链接", "🔍")
        
        kw_inner = tk.Frame(keyword_card, bg=THEME["bg_card"])
        kw_inner.pack(fill="x", padx=12, pady=(0, 4))
        
        self._label(
            kw_inner,
            "每行一个任务（关键词 或 https://www.pinterest.com/pin/...）",
            fg=THEME["text_muted"],
        ).pack(anchor="w", pady=(0, 4))
        
        # 多行文本框
        text_frame = tk.Frame(kw_inner, bg=THEME["border"], bd=1)
        text_frame.pack(fill="x")
        
        self.keyword_text = tk.Text(
            text_frame,
            bg=THEME["bg_input"],
            fg=THEME["text_primary"],
            insertbackground=THEME["accent"],
            relief="flat",
            bd=0,
            font=("Consolas", 10),
            height=8,
            wrap=tk.WORD,
            selectbackground=THEME["bg_hover"],
        )
        
        kw_scroll = tk.Scrollbar(text_frame, orient="vertical", command=self.keyword_text.yview)
        self.keyword_text.configure(yscrollcommand=kw_scroll.set)
        
        self.keyword_text.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        kw_scroll.pack(side="right", fill="y")
        
        # 示例提示
        example_text = (
            "示例:\n"
            "美食摄影\n"
            "minimalist home decor\n"
            "https://www.pinterest.com/pin/123456789/"
        )
        self.keyword_text.insert("1.0", example_text)
        self.keyword_text.config(fg=THEME["text_muted"])
        
        def on_focus_in(e):
            if self.keyword_text.get("1.0", tk.END).strip() == example_text.strip():
                self.keyword_text.delete("1.0", tk.END)
                self.keyword_text.config(fg=THEME["text_primary"])
        
        def on_focus_out(e):
            if not self.keyword_text.get("1.0", tk.END).strip():
                self.keyword_text.insert("1.0", example_text)
                self.keyword_text.config(fg=THEME["text_muted"])
        
        self.keyword_text.bind("<FocusIn>", on_focus_in)
        self.keyword_text.bind("<FocusOut>", on_focus_out)
        self._keyword_example = example_text
        
        # 清除按钮
        clear_btn = ModernButton(
            kw_inner, "清除内容", command=self._clear_keywords,
            style="secondary", padx=10, pady=4
        )
        clear_btn.pack(anchor="e", pady=4)
        
        # ── 参数设置 ──
        param_card = self._card(parent)
        self._section_header(param_card, "爬取参数", "⚙️")

        param_inner = tk.Frame(param_card, bg=THEME["bg_card"])
        param_inner.pack(fill="x", padx=12, pady=(0, 12))

        # 每层图片数
        self._build_slider_row(
            param_inner,
            label="每层图片数量",
            var=self.imgs_per_layer_var,
            min_val=3, max_val=50, step=1,
            unit="张",
        )

        # 层数
        self._build_slider_row(
            param_inner,
            label="爬取层级",
            var=self.max_layers_var,
            min_val=1, max_val=5, step=1,
            unit="层",
            hint="层数越多，图片越丰富但耗时越长",
        )

    def _build_slider_row(self, parent, label, var, min_val, max_val, step, unit="", hint=""):
        """构建滑块行 — 现代布局 + Canvas 自绘滑块"""
        outer = tk.Frame(parent, bg=THEME["bg_card"],
                         highlightthickness=1,
                         highlightbackground=THEME["border"])
        outer.pack(fill="x", pady=(0, 8), ipady=6)

        inner = tk.Frame(outer, bg=THEME["bg_card"])
        inner.pack(fill="x", padx=12)

        # ── 标签行：名称 + 数局显示 + 单位 + 加减按鈕 ──
        top = tk.Frame(inner, bg=THEME["bg_card"])
        top.pack(fill="x", pady=(4, 0))

        tk.Label(top, text=label,
                 bg=THEME["bg_card"], fg=THEME["text_secondary"],
                 font=("Segoe UI", 10)).pack(side="left")

        # 数值显示区域
        val_badge = tk.Frame(top, bg=THEME["bg_input"],
                             highlightthickness=1,
                             highlightbackground=THEME["border"])
        val_badge.pack(side="left", padx=10)

        tk.Label(val_badge, textvariable=var,
                 bg=THEME["bg_input"], fg=THEME["accent_glow"],
                 font=("Segoe UI", 13, "bold"),
                 width=3, anchor="center").pack(padx=8, pady=1)

        if unit:
            tk.Label(top, text=unit,
                     bg=THEME["bg_card"], fg=THEME["text_muted"],
                     font=("Segoe UI", 9)).pack(side="left")

        # 加减按鈕
        def dec(): var.set(max(min_val, var.get() - step))
        def inc(): var.set(min(max_val, var.get() + step))

        btn_cfg = dict(bg=THEME["bg_hover"], fg=THEME["text_primary"],
                       relief="flat", bd=0, cursor="hand2",
                       font=("Segoe UI", 12, "bold"), width=2)
        tk.Button(top, text="−", command=dec, **btn_cfg).pack(side="right", padx=(4, 0))
        tk.Button(top, text="+", command=inc, **btn_cfg).pack(side="right", padx=(8, 0))

        # ── Canvas 滑块 ──
        ModernSlider(
            inner, variable=var,
            from_=min_val, to=max_val, resolution=step,
        ).pack(fill="x", pady=(4, 2))

        # ── 最小/最大标注 ──
        range_row = tk.Frame(inner, bg=THEME["bg_card"])
        range_row.pack(fill="x")
        tk.Label(range_row, text=str(min_val),
                 bg=THEME["bg_card"], fg=THEME["text_muted"],
                 font=("Segoe UI", 8)).pack(side="left")
        tk.Label(range_row, text=str(max_val),
                 bg=THEME["bg_card"], fg=THEME["text_muted"],
                 font=("Segoe UI", 8)).pack(side="right")

        if hint:
            tk.Label(inner, text=hint,
                     bg=THEME["bg_card"], fg=THEME["text_muted"],
                     font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 0))
    
    def _build_log_panel(self, parent):
        """构建右侧日志面板"""
        # 标题
        header_frame = tk.Frame(parent, bg=THEME["bg_panel"], height=44)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)
        
        tk.Label(
            header_frame,
            text="📋 运行日志",
            font=("Segoe UI", 11, "bold"),
            bg=THEME["bg_panel"],
            fg=THEME["text_primary"],
        ).pack(side="left", padx=12, pady=8)
        
        # 清除日志按钮
        clear_log_btn = tk.Button(
            header_frame,
            text="清空",
            font=("Segoe UI", 9),
            bg=THEME["bg_card"],
            fg=THEME["text_muted"],
            relief="flat",
            cursor="hand2",
            command=lambda: self.log_panel.clear(),
            padx=8, pady=2,
        )
        clear_log_btn.pack(side="right", padx=8)
        
        # 分隔线
        sep = tk.Frame(parent, bg=THEME["border"], height=1)
        sep.pack(fill="x")
        
        # 日志区域
        self.log_panel = LogPanel(parent, height=20)
        self.log_panel.pack(fill="both", expand=True, padx=4, pady=4)
        
        # 欢迎消息
        self.log_panel.append("🎨 Pinterest 高清图片爬取工具 已启动")
        self.log_panel.append("📌 请在左侧配置爬取参数，然后点击「开始爬取」")
        self.log_panel.append("─" * 60)
    
    def _build_status_bar(self):
        """构建底部状态栏"""
        status_frame = tk.Frame(self.root, bg=THEME["bg_panel"], height=32)
        status_frame.pack(fill="x", side="bottom")
        status_frame.pack_propagate(False)
        
        # 进度条
        self.progress_bar = ttk.Progressbar(
            status_frame,
            style="Pinterest.Horizontal.TProgressbar",
            mode="indeterminate",
            length=200,
        )
        self.progress_bar.pack(side="left", padx=12, pady=8)
        
        # 状态文字
        self.status_var = tk.StringVar(value="⚡ 就绪")
        self.status_label = tk.Label(
            status_frame,
            textvariable=self.status_var,
            font=("Segoe UI", 9),
            bg=THEME["bg_panel"],
            fg=THEME["text_secondary"],
        )
        self.status_label.pack(side="left", padx=8)
        
        # 版本信息
        tk.Label(
            status_frame,
            text="v1.0 · Pinterest Crawler",
            font=("Segoe UI", 8),
            bg=THEME["bg_panel"],
            fg=THEME["text_muted"],
        ).pack(side="right", padx=12)
    
    # ─────────────────────────────────────────
    # 事件处理
    # ─────────────────────────────────────────
    def _browse_path(self):
        """浏览保存路径"""
        path = filedialog.askdirectory(title="选择图片保存目录")
        if path:
            self.save_path_var.set(path)
    
    def _clear_keywords(self):
        """清除关键词"""
        self.keyword_text.delete("1.0", tk.END)
        self.keyword_text.config(fg=THEME["text_primary"])
    
    def _open_save_dir(self):
        """打开保存目录"""
        path = self.save_path_var.get()
        if os.path.exists(path):
            os.startfile(path)
        else:
            messagebox.showinfo("提示", f"目录尚未创建:\n{path}")
    
    def _get_tasks(self):
        """获取任务列表"""
        content = self.keyword_text.get("1.0", tk.END).strip()
        if content == self._keyword_example.strip():
            return []
        
        tasks = [line.strip() for line in content.splitlines() if line.strip()]
        # 过滤掉纯注释行（以#开头）
        tasks = [t for t in tasks if not t.startswith("#")]
        return tasks
    
    def _start_crawl(self):
        """开始爬取"""
        # 验证输入
        tasks = self._get_tasks()
        if not tasks:
            messagebox.showwarning("提示", "请输入至少一个关键词或Pinterest链接！")
            return
        
        save_path = self.save_path_var.get().strip()
        if not save_path:
            messagebox.showwarning("提示", "请设置图片保存路径！")
            return
        
        # 确认目录可创建
        try:
            os.makedirs(save_path, exist_ok=True)
        except Exception as e:
            messagebox.showerror("错误", f"无法创建保存目录:\n{e}")
            return
        
        # 重置停止事件
        self.stop_event.clear()
        self.is_running = True
        
        # 更新UI状态
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.progress_bar.start(12)
        self.status_var.set("🔄 爬取中...")
        
        self.log_panel.append("=" * 60)
        self.log_panel.append(f"🚀 开始新一轮爬取任务")
        self.log_panel.append(f"📁 保存路径: {save_path}")
        self.log_panel.append(f"📋 任务数量: {len(tasks)}")
        self.log_panel.append(f"🔢 每层图片: {self.imgs_per_layer_var.get()} 张")
        self.log_panel.append(f"📊 爬取层级: {self.max_layers_var.get()} 层")
        self.log_panel.append("=" * 60)
        
        # 配置日志
        log_dir = os.path.join(save_path, "_logs")
        logger = setup_logger(log_dir)
        
        # 创建爬虫
        crawler = PinterestCrawler(
            save_root=save_path,
            imgs_per_layer=self.imgs_per_layer_var.get(),
            max_layers=self.max_layers_var.get(),
            logger=logger,
            log_callback=self._on_crawler_log,
            stop_event=self.stop_event,
        )
        self.crawler = crawler
        
        # 在后台线程运行
        def run_task():
            try:
                crawler.run(tasks)
            except Exception as e:
                self._on_crawler_log(f"❌ 爬虫异常: {e}")
            finally:
                self.root.after(0, self._on_crawl_finished)
        
        self.crawler_thread = threading.Thread(target=run_task, daemon=True)
        self.crawler_thread.start()
    
    def _stop_crawl(self):
        """停止爬取"""
        if self.crawler:
            self.crawler.stop()
        self.stop_event.set()
        self.status_var.set("⏹️ 正在停止...")
        self.log_panel.append("⏹️ 用户已请求停止，等待当前任务完成...")
    
    def _on_crawler_log(self, message: str):
        """爬虫日志回调（线程安全）"""
        self.root.after(0, lambda: self.log_panel.append(message))
        self.root.after(0, lambda: self.status_var.set(f"🔄 {message[:50]}..."))
    
    def _on_crawl_finished(self):
        """爬取完成回调"""
        self.is_running = False
        self.progress_bar.stop()
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_var.set("⚡ 任务完成，就绪")
        
        self.log_panel.append("─" * 60)
        self.log_panel.append("🎉 爬取任务已结束！")
        
        # 询问是否打开目录
        save_path = self.save_path_var.get()
        if os.path.exists(save_path):
            if messagebox.askyesno("完成", "爬取任务已完成！\n是否立即打开图片保存目录？"):
                os.startfile(save_path)
    
    def run(self):
        """运行应用"""
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        # 启动系统托盘图标（后台线程）
        self._start_tray()
        self.root.mainloop()

    # ── 系统托盘 ──────────────────────────────
    def _start_tray(self):
        """在后台线程启动系统托盘图标"""
        if not TRAY_AVAILABLE or self._pil_icon is None:
            return
        try:
            menu = pystray.Menu(
                TrayItem("显示主窗口", self._tray_show, default=True),
                pystray.Menu.SEPARATOR,
                TrayItem("开始爬取", lambda icon, item: self.root.after(0, self._start_crawl)),
                TrayItem("停止爬取", lambda icon, item: self.root.after(0, self._stop_crawl)),
                pystray.Menu.SEPARATOR,
                TrayItem("退出程序", self._tray_quit),
            )
            self._tray_icon = pystray.Icon(
                "PinterestCrawler",
                self._pil_icon,
                "Pinterest 爬取工具",
                menu,
            )
            tray_thread = threading.Thread(target=self._tray_icon.run, daemon=True)
            tray_thread.start()
        except Exception:
            pass

    def _tray_show(self, icon=None, item=None):
        """从托盘恢复显示窗口"""
        self.root.after(0, self.root.deiconify)
        self.root.after(0, self.root.lift)

    def _tray_quit(self, icon=None, item=None):
        """从托盘退出程序"""
        if self._tray_icon:
            self._tray_icon.stop()
        self.root.after(0, self.root.destroy)

    # ── 关闭处理 ──────────────────────────────
    def _on_close(self):
        """点击 X 时最小化到托盘，而不是直接退出"""
        if TRAY_AVAILABLE and self._tray_icon:
            # 隐藏窗口，继续在托盘运行
            self.root.withdraw()
        else:
            # 无托盘时直接询问退出
            if self.is_running:
                if messagebox.askyesno("确认退出", "爬取任务正在进行中！\n确定要退出吗？"):
                    if self.crawler:
                        self.crawler.stop()
                    self.root.destroy()
            else:
                self.root.destroy()


# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = PinterestCrawlerApp()
    app.run()
