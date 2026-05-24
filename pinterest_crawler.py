"""
Pinterest Image Crawler - 高清图片分层爬取工具
作者: AI 爬虫工程师
功能: 根据关键词或Pinterest链接进行分层爬取，收集高清图片
"""

import os
import re
import json as _json
import time
import random
import logging
import hashlib
import requests
import threading
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urlencode, quote
from typing import List, Optional, Set, Callable

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    StaleElementReferenceException, WebDriverException
)

try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER = True
except ImportError:
    WEBDRIVER_MANAGER = False

try:
    import undetected_chromedriver as uc
    UC_AVAILABLE = True
except ImportError:
    UC_AVAILABLE = False

# ─────────────────────────────────────────────
# 日志配置
# ─────────────────────────────────────────────
def setup_logger(log_dir: str) -> logging.Logger:
    """配置日志系统"""
    logger = logging.getLogger("PinterestCrawler")
    logger.setLevel(logging.DEBUG)
    
    # 防止重复添加handler
    if logger.handlers:
        logger.handlers.clear()
    
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 文件日志
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"crawler_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    return logger


# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────
def sanitize_folder_name(name: str) -> str:
    """清理文件夹名称，移除非法字符"""
    # 移除Windows文件名非法字符
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    # 截断过长名称
    name = name[:60].strip()
    return name if name else "未命名任务"


def extract_pin_id(url: str) -> Optional[str]:
    """从Pinterest URL中提取Pin ID"""
    patterns = [
        r'pinterest\.com/pin/(\d+)',
        r'pin\.it/(\w+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def is_pinterest_url(text: str) -> bool:
    """判断输入是否为Pinterest链接"""
    return bool(re.search(r'(pinterest\.com|pin\.it)', text, re.IGNORECASE))


def normalize_pinterest_url(url: str) -> str:
    """将区域域名（pt/uk/nl等）规范化为 www.pinterest.com"""
    return re.sub(
        r'https?://[a-z]{2,6}\.pinterest\.com',
        'https://www.pinterest.com',
        url,
    )


def upgrade_image_url(url: str) -> str:
    """将缩略图URL升级为高清原图URL"""
    if not url:
        return url
    
    # Pinterest图片URL模式替换为最高清版本
    # 优先使用 originals
    url = re.sub(r'/\d+x\d+/', '/originals/', url)
    url = re.sub(r'/\d+x/', '/originals/', url)
    url = re.sub(r'_b\.(jpg|jpeg|png|webp)', r'_o.\1', url, flags=re.IGNORECASE)
    
    # 如果没有 originals，尝试 736x（高清）
    if 'originals' not in url:
        url = re.sub(r'/\d{2,3}x/', '/736x/', url)
    
    return url


def random_sleep(min_s: float = 1.5, max_s: float = 4.0):
    """随机休眠，模拟人类行为"""
    time.sleep(random.uniform(min_s, max_s))


def human_scroll(driver, scroll_count: int = 3):
    """模拟人类滚动行为"""
    for _ in range(scroll_count):
        # 随机滚动距离
        scroll_distance = random.randint(400, 800)
        driver.execute_script(f"window.scrollBy(0, {scroll_distance});")
        random_sleep(0.8, 2.0)


# ─────────────────────────────────────────────
# 图片下载器
# ─────────────────────────────────────────────
class ImageDownloader:
    """负责图片下载与去重"""
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.pinterest.com/",
        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
    }
    
    def __init__(self, logger: logging.Logger, progress_callback: Optional[Callable] = None):
        self.logger = logger
        self.progress_callback = progress_callback
        self.downloaded_hashes: Set[str] = set()
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
    
    def download_image(self, url: str, save_path: str, filename: str) -> bool:
        """下载单张图片，返回是否成功"""
        # 尝试获取高清版本
        hd_url = upgrade_image_url(url)
        
        urls_to_try = [hd_url]
        if hd_url != url:
            urls_to_try.append(url)
        
        for try_url in urls_to_try:
            try:
                response = self.session.get(try_url, timeout=20, stream=True)
                if response.status_code != 200:
                    continue
                
                content = response.content
                if len(content) < 5000:  # 跳过太小的图片（可能是缩略图）
                    continue
                
                # 去重检查
                img_hash = hashlib.md5(content).hexdigest()
                if img_hash in self.downloaded_hashes:
                    self.logger.debug(f"跳过重复图片: {filename}")
                    return False
                self.downloaded_hashes.add(img_hash)
                
                # 确定扩展名
                content_type = response.headers.get('Content-Type', 'image/jpeg')
                ext = self._get_extension(try_url, content_type)
                
                full_path = os.path.join(save_path, f"{filename}{ext}")
                os.makedirs(save_path, exist_ok=True)
                
                with open(full_path, 'wb') as f:
                    f.write(content)
                
                self.logger.info(f"✅ 下载成功: {filename}{ext} ({len(content)//1024}KB)")
                if self.progress_callback:
                    self.progress_callback(f"已下载: {filename}{ext}")
                return True
                
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"下载失败 {try_url}: {e}")
                continue
        
        self.logger.warning(f"❌ 所有URL均下载失败: {url}")
        return False
    
    def _get_extension(self, url: str, content_type: str) -> str:
        """获取图片扩展名"""
        ext_map = {
            'image/jpeg': '.jpg',
            'image/jpg': '.jpg',
            'image/png': '.png',
            'image/webp': '.webp',
            'image/gif': '.gif',
        }
        
        # 从URL提取
        url_lower = url.lower().split('?')[0]
        for fmt in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
            if url_lower.endswith(fmt):
                return '.jpg' if fmt == '.jpeg' else fmt
        
        # 从Content-Type
        return ext_map.get(content_type.split(';')[0].strip(), '.jpg')


# ─────────────────────────────────────────────
# Pinterest 内部 JSON API（无需浏览器，无需登录）
# ─────────────────────────────────────────────
class PinterestAPI:
    """
    直接调用 Pinterest 内部 REST API。
    Pinterest 的 React 前端自身使用这些接口加载数据，
    无需登录即可访问基本搜索和相关图片数据。
    """

    BASE = "https://www.pinterest.com/resource"
    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.pinterest.com/",
        "X-Requested-With": "XMLHttpRequest",
        "X-APP-VERSION": "4cf24f4",
        "X-Pinterest-AppState": "active",
    }

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update(self._HEADERS)
        self._init_cookies()

    def _init_cookies(self):
        """访问首页获取 Session Cookie（csrftoken 等）"""
        try:
            r = self.session.get("https://www.pinterest.com/", timeout=15)
            if self.logger:
                self.logger.debug(f"API cookie 初始化: status={r.status_code}")
        except Exception as e:
            if self.logger:
                self.logger.debug(f"API cookie 初始化失败: {e}")

    def _get(self, endpoint: str, options: dict, source_url: str) -> Optional[dict]:
        """通用请求方法"""
        params = {
            "source_url": source_url,
            "data": _json.dumps({"options": options, "context": {}},
                                separators=(",", ":")),
            "_": str(int(time.time() * 1000)),
        }
        try:
            resp = self.session.get(
                f"{self.BASE}/{endpoint}/get/",
                params=params,
                timeout=20,
            )
            if resp.status_code == 200:
                return resp.json()
            if self.logger:
                self.logger.debug(f"API [{endpoint}] HTTP {resp.status_code}")
        except Exception as e:
            if self.logger:
                self.logger.debug(f"API [{endpoint}] 异常: {e}")
        return None

    # ── 公开方法 ─────────────────────────────────────
    def search_pins(self, query: str, count: int = 50) -> List[dict]:
        """关键词搜索（同时尝试两个端点）"""
        for endpoint in ["BaseSearchResource", "SearchResource"]:
            result = self._get(
                endpoint,
                {
                    "query": query,
                    "scope": "pins",
                    "page_size": min(count, 50),
                    "redux_normalize_feed": True,
                },
                f"/search/pins/?q={quote(query)}",
            )
            if result:
                pins = (
                    result.get("resource_response", {})
                          .get("data", {})
                          .get("results", [])
                )
                items = self._pins_to_items(pins)
                if items:
                    return items
        return []

    def get_pin_image(self, pin_id: str) -> str:
        """获取单个 Pin 的高清图片 URL（PinResource）"""
        result = self._get(
            "PinResource",
            {"id": pin_id, "field_set_key": "detailed"},
            f"/pin/{pin_id}/",
        )
        if not result:
            return ""
        data = result.get("resource_response", {}).get("data", {})
        return self._best_url(data.get("images", {}))

    def get_related_pins(self, pin_id: str, count: int = 50) -> List[dict]:
        """获取相关 Pin（RelatedPinFeedResource — More Like This）"""
        result = self._get(
            "RelatedPinFeedResource",
            {"pin_id": pin_id, "page_size": min(count, 50), "add_vase": True},
            f"/pin/{pin_id}/",
        )
        if not result:
            return []
        data = result.get("resource_response", {}).get("data", {})
        pins = data if isinstance(data, list) else data.get("results", [])
        return self._pins_to_items(pins)

    # ── 内部辅助 ─────────────────────────────────────
    def _best_url(self, images: dict) -> str:
        """从 images 字典中取最高清的 URL"""
        for key in ["orig", "736x", "474x", "236x"]:
            img = images.get(key, {})
            if isinstance(img, dict):
                url = img.get("url", "")
                if url and "pinimg.com" in url:
                    return url
        return ""

    def _pins_to_items(self, pins: list) -> List[dict]:
        """将 Pin JSON 数据转换为 {img_url, pin_url} 列表"""
        results: List[dict] = []
        seen: Set[str] = set()
        for pin in (pins or []):
            if not isinstance(pin, dict):
                continue
            pin_id = str(pin.get("id", ""))
            if not pin_id or pin_id in seen:
                continue
            seen.add(pin_id)
            img_url = self._best_url(pin.get("images", {}))
            if not img_url:
                continue
            results.append({
                "img_url": img_url,
                "pin_url": f"https://www.pinterest.com/pin/{pin_id}/",
            })
        return results


class PinterestCrawler:
    """Pinterest图片爬虫核心类"""
    
    PINTEREST_SEARCH_URL = "https://www.pinterest.com/search/pins/?q={query}"
    PINTEREST_PIN_URL = "https://www.pinterest.com/pin/{pin_id}/"
    
    def __init__(
        self,
        save_root: str,
        imgs_per_layer: int = 10,
        max_layers: int = 2,
        logger: Optional[logging.Logger] = None,
        log_callback: Optional[Callable] = None,
        stop_event: Optional[threading.Event] = None,
    ):
        self.save_root = save_root
        self.imgs_per_layer = imgs_per_layer
        self.max_layers = max_layers
        self.logger = logger or logging.getLogger("PinterestCrawler")
        self.log_callback = log_callback
        self.stop_event = stop_event or threading.Event()
        self.driver: Optional[webdriver.Chrome] = None
        self.downloader = ImageDownloader(self.logger, self._emit_log)
        self.api = PinterestAPI(self.logger)   # ← Pinterest 内部 API
        self.batch_dir = self._create_batch_dir()
    
    def _emit_log(self, message: str, level: str = "INFO"):
        """同时记录日志和回调UI"""
        if level == "INFO":
            self.logger.info(message)
        elif level == "WARNING":
            self.logger.warning(message)
        elif level == "ERROR":
            self.logger.error(message)
        if self.log_callback:
            self.log_callback(message)
    
    def _create_batch_dir(self) -> str:
        """创建批次目录"""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        batch_dir = os.path.join(self.save_root, timestamp)
        os.makedirs(batch_dir, exist_ok=True)
        self._emit_log(f"📁 批次目录已创建: {batch_dir}")
        return batch_dir
    
    def _init_driver(self) -> webdriver.Chrome:
        """初始化 Chrome 浏览器（优先使用 undetected-chromedriver 规避检测）"""
        self._emit_log("🚀 正在启动浏览器...")

        # ── 公共 Chrome 参数 ──
        common_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--window-size=1920,1080",
            "--lang=zh-CN,zh;q=0.9",
            "--disable-blink-features=AutomationControlled",
            "--disable-notifications",
        ]

        # ── 优先使用 undetected_chromedriver ──
        if UC_AVAILABLE:
            try:
                options = uc.ChromeOptions()
                for arg in common_args:
                    options.add_argument(arg)
                driver = uc.Chrome(options=options, headless=True, use_subprocess=True)
                self._emit_log("✅ 浏览器启动成功（undetected 模式）")
                return driver
            except Exception as e:
                self._emit_log(f"⚠️ undetected 模式失败，切换普通模式: {e}", "WARNING")

        # ── 普通 Selenium 回退 ──
        options = Options()
        options.add_argument("--headless=new")
        for arg in common_args:
            options.add_argument(arg)
        options.add_experimental_option(
            "excludeSwitches", ["enable-automation", "enable-logging"]
        )
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
        prefs = {
            "profile.managed_default_content_settings.images": 1,
            "profile.default_content_setting_values.notifications": 2,
        }
        options.add_experimental_option("prefs", prefs)

        try:
            if WEBDRIVER_MANAGER:
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
            else:
                driver = webdriver.Chrome(options=options)

            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN','zh']});
                    window.chrome = { runtime: {} };
                """
            })
            self._emit_log("✅ 浏览器启动成功")
            return driver
        except WebDriverException as e:
            self._emit_log(f"❌ 浏览器启动失败: {e}", "ERROR")
            raise

    def _wait_for_images(self, timeout: int = 20):
        """等待页面图片加载（与 v1.0.5 一致：任意 img[src] 即可）"""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "img[src]"))
            )
        except TimeoutException:
            pass
        # 记录页面标题，帮助诊断是否被拦截
        try:
            self._emit_log(f"📄 页面: {self.driver.title[:50]}")
        except Exception:
            pass

    # ── JavaScript 通用提取（不依赖具体 CSS 选择器）──────────────
    _JS_EXTRACT = """
    (function(maxCount) {
        var results = [];
        var seen = {};
        var allImgs = document.querySelectorAll('img');

        allImgs.forEach(function(img) {
            if (results.length >= maxCount) return;

            // 从 src / data-src / srcset 中获取图片 URL
            var src = img.getAttribute('src') || img.getAttribute('data-src') || '';
            if (!src || src.indexOf('pinimg.com') === -1) {
                // 尝试 srcset（取分辨率最高的最后一项）
                var ss = img.getAttribute('srcset') || '';
                if (ss && ss.indexOf('pinimg.com') !== -1) {
                    var parts = ss.split(',');
                    var last  = parts[parts.length - 1].trim().split(/\\s+/)[0];
                    if (last.indexOf('pinimg.com') !== -1) src = last;
                }
            }
            if (!src || src.indexOf('pinimg.com') === -1) return;
            if (seen[src]) return;
            seen[src] = true;

            // 向上遍历 DOM，找最近的 /pin/ 链接
            var el = img.parentElement;
            var pinUrl = null;
            var depth  = 0;
            while (el && depth < 12) {
                if (el.tagName === 'A') {
                    var href = el.getAttribute('href') || '';
                    if (href.indexOf('/pin/') !== -1) {
                        pinUrl = href.indexOf('http') === 0
                            ? href
                            : 'https://www.pinterest.com' + href;
                        break;
                    }
                }
                el = el.parentElement;
                depth++;
            }
            if (pinUrl) {
                results.push({img_url: src, pin_url: pinUrl});
            }
        });
        return results;
    })(arguments[0]);
    """

    def _extract_image_urls_from_page(self, max_count: int) -> List[dict]:
        """
        从页面提取图片 — CSS 选择器（v1.0.5 方法，已验证可靠）为主，JS 为备用
        返回: [{"img_url": ..., "pin_url": ...}, ...]
        """
        results: List[dict] = []
        seen_urls: Set[str] = set()
        scroll_attempts = 0
        max_scroll = max(6, max_count // 2)

        while len(results) < max_count and scroll_attempts < max_scroll:
            if self.stop_event.is_set():
                break

            try:
                # 主方法：CSS 选择器（v1.0.5 经典步骤）
                pin_elements = self.driver.find_elements(
                    By.CSS_SELECTOR, "a[href*='/pin/']"
                )
                for elem in pin_elements:
                    if len(results) >= max_count:
                        break
                    try:
                        href = elem.get_attribute("href") or ""
                        if "/pin/" not in href:
                            continue
                        try:
                            img = elem.find_element(By.TAG_NAME, "img")
                        except NoSuchElementException:
                            continue
                        # 依次尝试 src / data-src / srcset
                        img_src = img.get_attribute("src") or ""
                        if not img_src or "pinimg.com" not in img_src:
                            img_src = img.get_attribute("data-src") or ""
                        if not img_src or "pinimg.com" not in img_src:
                            ss = img.get_attribute("srcset") or ""
                            if "pinimg.com" in ss:
                                parts = ss.split(",")
                                img_src = parts[-1].strip().split()[0]
                        if not img_src or "pinimg.com" not in img_src:
                            continue
                        img_src = upgrade_image_url(img_src)
                        if img_src in seen_urls:
                            continue
                        seen_urls.add(img_src)
                        if href.startswith("/"):
                            href = "https://www.pinterest.com" + href
                        results.append({"img_url": img_src, "pin_url": href})
                    except (StaleElementReferenceException, Exception):
                        continue
            except Exception as e:
                self.logger.debug(f"提取图片出错: {e}")

            if len(results) < max_count:
                human_scroll(self.driver, scroll_count=2)
                scroll_attempts += 1
                random_sleep(1.5, 3.0)

        # 备用：CSS 没找到时用 JS 内容提取
        if not results:
            try:
                raw = self.driver.execute_script(self._JS_EXTRACT, max_count * 3) or []
                for item in raw:
                    if len(results) >= max_count:
                        break
                    iu = upgrade_image_url(item.get("img_url", ""))
                    pu = item.get("pin_url", "")
                    if iu and pu and iu not in seen_urls:
                        seen_urls.add(iu)
                        results.append({"img_url": iu, "pin_url": pu})
            except Exception as e:
                self.logger.debug(f"JS备用提取出错: {e}")

        self._emit_log(f"📸 当前页面找到 {len(results)} 张图片")
        return results[:max_count]

    def _extract_page_keywords(self) -> str:
        """从当前页面标题提取关键词，用于搜索相关内容"""
        try:
            title = self.driver.title
            # 去掉 Pinterest 标准后缀
            title = re.sub(r'\s*[-–|]\s*Pinterest.*$', '', title, flags=re.IGNORECASE).strip()
            # 去掉 "Pin en/on/de" 前缀
            title = re.sub(r'^Pin\s+(en|on|de|in|su|vom|van|sur)\s+', '', title, flags=re.IGNORECASE).strip()
            if title and len(title) > 2:
                self._emit_log(f"🔑 提取关键词: {title}")
                return title
        except Exception:
            pass
        return ""

    def _search_for_images(self, keyword: str, max_count: int) -> List[dict]:
        """用关键词搜索 Pinterest 图片（不需要登录）"""
        search_url = self.PINTEREST_SEARCH_URL.format(query=quote(keyword))
        self._emit_log(f"🔎 关键词搜索: {keyword}")
        try:
            self.driver.get(search_url)
            random_sleep(3.0, 5.0)
            self._wait_for_images()
            human_scroll(self.driver, scroll_count=4)
            random_sleep(2.0, 3.0)
            results = self._extract_image_urls_from_page(max_count)
            self._emit_log(f"📸 搜索结果: {len(results)} 张")
            return results
        except Exception as e:
            self._emit_log(f"❌ 关键词搜索失败: {e}", "ERROR")
            return []

    def _get_related_pins(self, pin_url: str, max_count: int) -> List[dict]:
        """
        获取相关图片。优先 API，其次浏览器。
        重要：不对 URL 做区域规范化，保留原始域名（如 pt.pinterest.com）。
        """
        pin_id = extract_pin_id(pin_url)

        # ── 优先：RelatedPinFeedResource API ──
        if pin_id:
            self._emit_log(f"🌐 API 获取相关图片 (pin/{pin_id})")
            related = self.api.get_related_pins(pin_id, count=max_count * 2)
            if related:
                self._emit_log(f"🔗 API 找到 {len(related)} 张相关图片")
                return related[:max_count]

        # ── 备用：浏览器 CSS 选择器（v1.0.5 经典方法）──
        try:
            if not self.driver:
                self.driver = self._init_driver()
            self._emit_log(f"🔍 浏览器访问Pin页: {pin_url}")
            self.driver.get(pin_url)   # 保留原始 URL，不做域名规范化
            random_sleep(3.0, 5.0)
            self._wait_for_images()
            human_scroll(self.driver, scroll_count=3)
            random_sleep(2.0, 3.5)

            related_results: List[dict] = []
            seen_urls: Set[str] = set()
            scroll_attempts = 0
            max_scroll = max(6, max_count // 2)
            current_pin_id = pin_id

            while len(related_results) < max_count and scroll_attempts < max_scroll:
                if self.stop_event.is_set():
                    break
                try:
                    pin_links = self.driver.find_elements(
                        By.CSS_SELECTOR, "a[href*='/pin/']"
                    )
                    for link in pin_links:
                        if len(related_results) >= max_count:
                            break
                        try:
                            href = link.get_attribute("href") or ""
                            if "/pin/" not in href:
                                continue
                            if extract_pin_id(href) == current_pin_id:
                                continue
                            try:
                                img = link.find_element(By.TAG_NAME, "img")
                            except NoSuchElementException:
                                continue
                            img_src = img.get_attribute("src") or ""
                            if not img_src or "pinimg.com" not in img_src:
                                img_src = img.get_attribute("data-src") or ""
                            if not img_src or "pinimg.com" not in img_src:
                                ss = img.get_attribute("srcset") or ""
                                if "pinimg.com" in ss:
                                    img_src = ss.split(",")[-1].strip().split()[0]
                            if not img_src or "pinimg.com" not in img_src:
                                continue
                            img_src = upgrade_image_url(img_src)
                            if img_src in seen_urls:
                                continue
                            seen_urls.add(img_src)
                            if href.startswith("/"):
                                href = "https://www.pinterest.com" + href
                            related_results.append({"img_url": img_src, "pin_url": href})
                        except (StaleElementReferenceException, Exception):
                            continue
                except Exception as e:
                    self.logger.debug(f"提取相关图片出错: {e}")

                if len(related_results) < max_count:
                    human_scroll(self.driver, scroll_count=2)
                    scroll_attempts += 1
                    random_sleep(1.5, 3.0)

            if related_results:
                self._emit_log(f"🔗 浏览器找到 {len(related_results)} 张相关图片")
                return related_results[:max_count]

        except Exception as e:
            self._emit_log(f"⚠️ 浏览器获取相关图片失败: {e}", "WARNING")

        self._emit_log("⚠️ 未找到相关图片，跳过", "WARNING")
        return []

    def _process_keyword_task(self, keyword: str, task_dir: str):
        """处理关键词任务 — 优先用内部 API，浏览器为备用"""
        self._emit_log(f"🔎 搜索关键词: {keyword}")

        layer1_dir = os.path.join(task_dir, "第一层-最相关")
        os.makedirs(layer1_dir, exist_ok=True)

        # ── 优先：直接调用 Pinterest 内部搜索 API ──
        self._emit_log("🌐 通过 API 搜索...", "INFO")
        layer1_pins = self.api.search_pins(keyword, count=self.imgs_per_layer * 3)

        if not layer1_pins:
            # ── 备用：开起浏览器搜索 ──
            self._emit_log("🔄 API 返回空，开起浏览器搜索...", "WARNING")
            if not self.driver:
                self.driver = self._init_driver()
            search_url = self.PINTEREST_SEARCH_URL.format(query=quote(keyword))
            self.driver.get(search_url)
            random_sleep(3.0, 5.0)
            self._wait_for_images()
            human_scroll(self.driver, scroll_count=4)
            random_sleep(2.0, 3.5)
            layer1_pins = self._extract_image_urls_from_page(self.imgs_per_layer)

        # 下载第一层
        self._emit_log(f"📥 第一层：抓取最相关图片（目标: {self.imgs_per_layer} 张）")
        downloaded_count = 0
        for i, pin_info in enumerate(layer1_pins[:self.imgs_per_layer]):
            if self.stop_event.is_set():
                return
            filename = f"L1_{i+1:03d}"
            if self.downloader.download_image(pin_info["img_url"], layer1_dir, filename):
                downloaded_count += 1
            random_sleep(0.3, 1.0)

        self._emit_log(f"✅ 第一层完成，下载 {downloaded_count} 张")

        if self.max_layers >= 2:
            self._process_extended_layers(layer1_pins[:self.imgs_per_layer], task_dir)

    def _process_url_task(self, url: str, task_dir: str):
        """处理Pinterest链接任务 — API 优先，浏览器保留原始 URL"""
        pin_id = extract_pin_id(url)
        self._emit_log(f"🔗 处理Pin链接: {url} (ID: {pin_id})")

        layer1_dir = os.path.join(task_dir, "第一层-最相关")
        os.makedirs(layer1_dir, exist_ok=True)
        self._emit_log("📥 第一层：下载原始Pin图片")
        downloaded_l1 = 0

        # ── 优先： API 直接获取主图 ──
        if pin_id:
            img_url = self.api.get_pin_image(pin_id)
            if img_url:
                if self.downloader.download_image(img_url, layer1_dir, "L1_001"):
                    downloaded_l1 = 1

        # ── 备用：浏览器，使用原始 URL ──
        if downloaded_l1 == 0:
            if not self.driver:
                self.driver = self._init_driver()
            self.driver.get(url)   # 保留原始 URL，不做域名规范化
            random_sleep(3.0, 5.0)
            self._wait_for_images()
            # 先用 CSS 选择器
            seen_l1: Set[str] = set()
            for elem in self.driver.find_elements(
                By.CSS_SELECTOR, "img[src*='pinimg.com']"
            )[:10]:
                if downloaded_l1 >= 1:
                    break
                try:
                    src = upgrade_image_url(elem.get_attribute("src") or "")
                    if src and src not in seen_l1:
                        seen_l1.add(src)
                        if self.downloader.download_image(src, layer1_dir, "L1_001"):
                            downloaded_l1 = 1
                except Exception:
                    continue

        self._emit_log(f"✅ 第一层完成，下载 {downloaded_l1} 张")
        if self.max_layers >= 2:
            self._process_extended_layers([{"img_url": "", "pin_url": url}], task_dir)

    def _process_extended_layers(self, source_pins: List[dict], task_dir: str):
        """处理延伸层（第二层及以上）"""
        ext_dir = os.path.join(task_dir, "延申-扩展")
        os.makedirs(ext_dir, exist_ok=True)
        
        self._emit_log(f"🌿 延伸层：从 {len(source_pins)} 个Pin顺藤摸瓜抓取相关图片")
        
        total_downloaded = 0
        total_target = self.imgs_per_layer * (self.max_layers - 1)
        
        # 遍历第一层的每个Pin，获取其相关图片
        per_pin_count = max(1, self.imgs_per_layer // max(1, len(source_pins)))
        
        for layer in range(2, self.max_layers + 1):
            if self.stop_event.is_set():
                break
            
            self._emit_log(f"📥 第 {layer} 层延伸（目标: {self.imgs_per_layer} 张）")
            layer_count = 0
            
            for pin_idx, pin_info in enumerate(source_pins):
                if self.stop_event.is_set():
                    break
                
                if not pin_info.get("pin_url"):
                    continue
                
                remaining = self.imgs_per_layer - layer_count
                if remaining <= 0:
                    break
                
                fetch_count = min(per_pin_count + (2 if pin_idx < 3 else 0), remaining)
                
                related_pins = self._get_related_pins(pin_info["pin_url"], fetch_count)
                
                for i, rel_pin in enumerate(related_pins):
                    if self.stop_event.is_set():
                        break
                    filename = f"L{layer}_{total_downloaded+1:04d}"
                    if self.downloader.download_image(rel_pin["img_url"], ext_dir, filename):
                        total_downloaded += 1
                        layer_count += 1
                    random_sleep(0.5, 1.5)
                
                random_sleep(1.5, 3.0)
            
            self._emit_log(f"✅ 第 {layer} 层完成，本层下载 {layer_count} 张")
        
        self._emit_log(f"🎉 延伸层总计下载: {total_downloaded} 张")
    
    def run(self, tasks: List[str]):
        """主运行入口"""
        self._emit_log(f"🚀 开始爬取任务，共 {len(tasks)} 个")
        
        try:
            self.driver = self._init_driver()
            
            for task_idx, task in enumerate(tasks):
                if self.stop_event.is_set():
                    self._emit_log("⏹️ 用户已停止任务")
                    break
                
                task = task.strip()
                if not task:
                    continue
                
                self._emit_log(f"\n{'='*50}")
                self._emit_log(f"📌 任务 [{task_idx+1}/{len(tasks)}]: {task}")
                
                # 确定任务文件夹名
                if is_pinterest_url(task):
                    pin_id = extract_pin_id(task)
                    folder_name = sanitize_folder_name(f"Pin_{pin_id}" if pin_id else "Pin_URL")
                else:
                    folder_name = sanitize_folder_name(task)
                
                task_dir = os.path.join(self.batch_dir, folder_name)
                os.makedirs(task_dir, exist_ok=True)
                
                self._emit_log(f"📁 任务目录: {task_dir}")
                
                try:
                    if is_pinterest_url(task):
                        self._process_url_task(task, task_dir)
                    else:
                        self._process_keyword_task(task, task_dir)
                except Exception as e:
                    self._emit_log(f"❌ 任务 [{task}] 失败: {e}", "ERROR")
                
                # 任务间随机等待
                if task_idx < len(tasks) - 1:
                    wait_time = random.uniform(3.0, 6.0)
                    self._emit_log(f"⏳ 等待 {wait_time:.1f}s 后继续下一任务...")
                    time.sleep(wait_time)
            
            self._emit_log(f"\n{'='*50}")
            self._emit_log(f"🎉 所有任务完成！图片保存于: {self.batch_dir}")
            
        except Exception as e:
            self._emit_log(f"❌ 爬虫运行错误: {e}", "ERROR")
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                    self._emit_log("🔒 浏览器已关闭")
                except Exception:
                    pass
    
    def stop(self):
        """停止爬取"""
        self.stop_event.set()
        self._emit_log("⏹️ 正在停止...")
