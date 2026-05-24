# -*- coding: utf-8 -*-
"""
Pinterest 爬虫测试脚本
逐步验证各功能模块是否正常工作
运行方式: python test_crawler.py
"""

import sys
import os
import time
import tempfile

# Windows 终端强制 UTF-8 输出
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ───────────────────────────────────────
# 工具函数
# ───────────────────────────────────────
def ok(msg):    print(f"  [PASS] {msg}")
def fail(msg):  print(f"  [FAIL] {msg}")
def info(msg):  print(f"  [INFO] {msg}")
def header(msg): print(f"\n{'─'*55}\n[TEST] {msg}\n{'─'*55}")

passed = 0
failed = 0

def check(name, fn):
    global passed, failed
    try:
        fn()
        ok(name)
        passed += 1
    except Exception as e:
        fail(f"{name}  =>  {e}")
        failed += 1


# ───────────────────────────────────────
# 测试 1：依赖导入
# ───────────────────────────────────────
header("测试 1：依赖包导入")

check("selenium 导入", lambda: __import__("selenium"))
check("webdriver_manager 导入", lambda: __import__("webdriver_manager"))
check("requests 导入", lambda: __import__("requests"))
check("PIL (Pillow) 导入", lambda: __import__("PIL"))
check("tkinter 导入", lambda: __import__("tkinter"))


# ───────────────────────────────────────
# 测试 2：核心工具函数
# ───────────────────────────────────────
header("测试 2：工具函数")

from pinterest_crawler import (
    sanitize_folder_name,
    extract_pin_id,
    is_pinterest_url,
    upgrade_image_url,
)

def test_sanitize():
    assert sanitize_folder_name("美食摄影/写真") == "美食摄影_写真"
    assert sanitize_folder_name("hello world") == "hello world"
    assert sanitize_folder_name("a" * 100) == "a" * 60  # 截断到60字符
check("文件夹名称清理 (sanitize_folder_name)", test_sanitize)

def test_pin_id():
    url = "https://www.pinterest.com/pin/123456789/"
    assert extract_pin_id(url) == "123456789"
    assert extract_pin_id("https://www.google.com") is None
check("提取 Pin ID (extract_pin_id)", test_pin_id)

def test_is_url():
    assert is_pinterest_url("https://www.pinterest.com/pin/123/") == True
    assert is_pinterest_url("美食摄影") == False
    assert is_pinterest_url("pin.it/AbCdEf") == True
check("Pinterest URL 识别 (is_pinterest_url)", test_is_url)

def test_upgrade_url():
    thumb = "https://i.pinimg.com/236x/ab/cd/ef/abcdef.jpg"
    hd    = upgrade_image_url(thumb)
    assert "originals" in hd or "736x" in hd, f"升级失败: {hd}"

    orig = "https://i.pinimg.com/originals/ab/cd/ef/abcdef.jpg"
    assert upgrade_image_url(orig) == orig  # 已是最高清，不应改变
check("图片 URL 升级为高清 (upgrade_image_url)", test_upgrade_url)


# ───────────────────────────────────────
# 测试 3：文件夹结构创建
# ───────────────────────────────────────
header("测试 3：文件夹结构")

import threading
from pinterest_crawler import PinterestCrawler, setup_logger

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:

    def test_batch_dir():
        stop = threading.Event()
        crawler = PinterestCrawler(
            save_root=tmpdir,
            imgs_per_layer=3,
            max_layers=2,
            stop_event=stop,
        )
        assert os.path.isdir(crawler.batch_dir), "批次目录未创建"
    check("批次目录自动创建", test_batch_dir)

    def test_logger():
        import logging
        log_dir = os.path.join(tmpdir, "_logs")
        logger = setup_logger(log_dir)
        logger.info("测试日志")
        assert os.path.isdir(log_dir)
        log_files = os.listdir(log_dir)
        assert len(log_files) > 0, "日志文件未创建"
        # 关闭所有 handler，释放文件锁（Windows 需要）
        for h in logger.handlers[:]:
            h.close()
            logger.removeHandler(h)
    check("日志文件创建", test_logger)


# ───────────────────────────────────────
# 测试 4：图片下载器（下载真实图片）
# ───────────────────────────────────────
header("测试 4：图片下载器（需要网络）")

from pinterest_crawler import ImageDownloader
import logging

with tempfile.TemporaryDirectory() as tmpdir:
    logger = logging.getLogger("test")
    downloader = ImageDownloader(logger)

    # 用公开大图测试下载（> 5KB 才能通过质量过滤）
    TEST_IMG_URL = (
        "https://upload.wikimedia.org/wikipedia/commons/"
        "a/a7/Camponotus_flavomarginatus_ant.jpg"
    )

    def test_download():
        result = downloader.download_image(TEST_IMG_URL, tmpdir, "test_img")
        files = os.listdir(tmpdir)
        assert result == True or len(files) > 0, "下载结果异常"
        info(f"下载文件: {files}")
    check("图片下载（Wikimedia 测试图）", test_download)

    def test_dedup():
        # 同一张图片下载两次，第二次应该返回 False（去重）
        downloader2 = ImageDownloader(logger)
        downloader2.download_image(TEST_IMG_URL, tmpdir, "dedup_1")
        result2 = downloader2.download_image(TEST_IMG_URL, tmpdir, "dedup_2")
        assert result2 == False, "去重失败，同一张图片被重复下载"
    check("图片去重（MD5 Hash）", test_dedup)


# ───────────────────────────────────────
# 测试 5：Chrome 浏览器（无头模式）
# ───────────────────────────────────────
header("测试 5：Chrome 无头浏览器（需要 Chrome 已安装）")

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

def test_browser():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,720")
    
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception:
        driver = webdriver.Chrome(options=options)
    
    try:
        driver.get("https://www.google.com")
        title = driver.title
        assert "Google" in title, f"页面标题异常: {title}"
        info(f"已成功访问 Google，标题: {title}")
    finally:
        driver.quit()

check("Chrome 无头浏览器启动 + 访问页面", test_browser)


# ───────────────────────────────────────
# 测试 6：UI 模块导入（不打开窗口）
# ───────────────────────────────────────
header("测试 6：UI 模块语法检查")

def test_ui_import():
    import ast
    with open("app.py", "r", encoding="utf-8") as f:
        source = f.read()
    ast.parse(source)  # 语法检查
check("app.py 语法无错误", test_ui_import)


# ───────────────────────────────────────
# 汇总结果
# ───────────────────────────────────────
total = passed + failed
print(f"\n{'='*50}")
print(f"📊 测试结果: {passed}/{total} 通过")
if failed == 0:
    print("🎉 所有测试通过！软件可以正常使用。")
    print("\n▶ 启动软件：python app.py")
else:
    print(f"⚠️  {failed} 个测试失败，请根据上面的错误信息排查。")
print("="*50)
