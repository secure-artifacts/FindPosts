"""
Pinterest Image Crawler - 高清图片分层爬取工具
作者: AI 爬虫工程师
功能: 根据关键词或Pinterest链接进行分层爬取，收集高清图片
"""

import os
import re
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
# Pinterest 爬虫核心
# ─────────────────────────────────────────────
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
        """初始化 Chrome 无头浏览器"""
        self._emit_log("🚀 正在启动浏览器...")
        
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--lang=zh-CN,zh;q=0.9")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        try:
            if WEBDRIVER_MANAGER:
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
            else:
                driver = webdriver.Chrome(options=options)
            
            # 隐藏 webdriver 特征
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            })
            
            self._emit_log("✅ 浏览器启动成功")
            return driver
            
        except WebDriverException as e:
            self._emit_log(f"❌ 浏览器启动失败: {e}", "ERROR")
            raise
    
    def _wait_for_images(self, timeout: int = 15):
        """等待页面图片加载完成"""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "img[src]"))
            )
        except TimeoutException:
            self._emit_log("⚠️ 等待图片超时，继续处理...", "WARNING")
    
    def _extract_image_urls_from_page(self, max_count: int) -> List[dict]:
        """
        从当前页面提取图片信息(url + pin_url)
        返回: [{"img_url": ..., "pin_url": ...}, ...]
        """
        results = []
        seen_urls: Set[str] = set()
        
        # 滚动加载更多内容
        scroll_attempts = 0
        max_scroll = max(5, max_count // 3)
        
        while len(results) < max_count and scroll_attempts < max_scroll:
            if self.stop_event.is_set():
                break
            
            try:
                # 查找所有图片容器（Pin卡片）
                pin_elements = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "[data-grid-item] a[href*='/pin/'], div[data-test-id='pin'] a[href*='/pin/']"
                )
                
                # 备用选择器
                if not pin_elements:
                    pin_elements = self.driver.find_elements(
                        By.CSS_SELECTOR,
                        "a[href*='/pin/']"
                    )
                
                for elem in pin_elements:
                    if len(results) >= max_count:
                        break
                    try:
                        href = elem.get_attribute("href") or ""
                        if "/pin/" not in href:
                            continue
                        
                        # 提取图片
                        img = None
                        try:
                            img = elem.find_element(By.TAG_NAME, "img")
                        except NoSuchElementException:
                            pass
                        
                        if not img:
                            continue
                        
                        img_src = img.get_attribute("src") or img.get_attribute("data-src") or ""
                        
                        # 过滤非图片URL
                        if not img_src or "pinimg.com" not in img_src:
                            continue
                        
                        # 升级为高清
                        img_src = upgrade_image_url(img_src)
                        
                        if img_src in seen_urls:
                            continue
                        seen_urls.add(img_src)
                        
                        # 确保pin_url是完整URL
                        if href.startswith("/"):
                            href = "https://www.pinterest.com" + href
                        
                        results.append({"img_url": img_src, "pin_url": href})
                        
                    except (StaleElementReferenceException, Exception):
                        continue
                
            except Exception as e:
                self.logger.debug(f"提取图片时出错: {e}")
            
            if len(results) < max_count:
                human_scroll(self.driver, scroll_count=2)
                scroll_attempts += 1
                random_sleep(1.5, 3.0)
        
        self._emit_log(f"📸 当前页面找到 {len(results)} 张图片")
        return results[:max_count]
    
    def _get_related_pins(self, pin_url: str, max_count: int) -> List[dict]:
        """进入Pin详情页，获取'More like this'相关图片"""
        try:
            self._emit_log(f"🔍 访问Pin详情页: {pin_url}")
            self.driver.get(pin_url)
            random_sleep(2.5, 4.0)
            self._wait_for_images()
            
            # 滚动到"More like this"区域
            human_scroll(self.driver, scroll_count=3)
            random_sleep(2.0, 3.5)
            
            # 继续滚动加载相关内容
            related_results = []
            seen_urls: Set[str] = set()
            scroll_attempts = 0
            max_scroll = max(6, max_count // 2)
            
            while len(related_results) < max_count and scroll_attempts < max_scroll:
                if self.stop_event.is_set():
                    break
                
                try:
                    # "More like this" 区域的图片
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
                            
                            # 排除当前Pin自身
                            current_pin_id = extract_pin_id(pin_url)
                            link_pin_id = extract_pin_id(href)
                            if link_pin_id and link_pin_id == current_pin_id:
                                continue
                            
                            img = None
                            try:
                                img = link.find_element(By.TAG_NAME, "img")
                            except NoSuchElementException:
                                pass
                            
                            if not img:
                                continue
                            
                            img_src = img.get_attribute("src") or img.get_attribute("data-src") or ""
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
                    self.logger.debug(f"获取相关图片时出错: {e}")
                
                if len(related_results) < max_count:
                    human_scroll(self.driver, scroll_count=2)
                    scroll_attempts += 1
                    random_sleep(1.5, 3.0)
            
            self._emit_log(f"🔗 找到 {len(related_results)} 张相关图片")
            return related_results[:max_count]
            
        except Exception as e:
            self._emit_log(f"❌ 获取相关图片失败: {e}", "ERROR")
            return []
    
    def _process_keyword_task(self, keyword: str, task_dir: str):
        """处理关键词任务"""
        self._emit_log(f"🔎 搜索关键词: {keyword}")
        
        # 构建搜索URL
        search_url = self.PINTEREST_SEARCH_URL.format(query=quote(keyword))
        
        try:
            self.driver.get(search_url)
            random_sleep(3.0, 5.0)
            self._wait_for_images()
            human_scroll(self.driver, scroll_count=3)
            random_sleep(2.0, 3.5)
            
            # 第一层：搜索结果主图
            layer1_dir = os.path.join(task_dir, "第一层-最相关")
            os.makedirs(layer1_dir, exist_ok=True)
            
            self._emit_log(f"📥 第一层：抓取最相关图片（目标: {self.imgs_per_layer} 张）")
            layer1_pins = self._extract_image_urls_from_page(self.imgs_per_layer)
            
            # 下载第一层图片
            downloaded_count = 0
            for i, pin_info in enumerate(layer1_pins):
                if self.stop_event.is_set():
                    return
                filename = f"L1_{i+1:03d}"
                if self.downloader.download_image(pin_info["img_url"], layer1_dir, filename):
                    downloaded_count += 1
                random_sleep(0.5, 1.5)
            
            self._emit_log(f"✅ 第一层完成，下载 {downloaded_count} 张")
            
            # 第二层及以上：顺藤摸瓜
            if self.max_layers >= 2:
                self._process_extended_layers(layer1_pins, task_dir)
                
        except Exception as e:
            self._emit_log(f"❌ 关键词任务失败: {e}", "ERROR")
    
    def _process_url_task(self, url: str, task_dir: str):
        """处理Pinterest链接任务"""
        pin_id = extract_pin_id(url)
        self._emit_log(f"🔗 处理Pin链接: {url} (ID: {pin_id})")
        
        try:
            self.driver.get(url)
            random_sleep(3.0, 5.0)
            self._wait_for_images()
            
            # 第一层：原始Pin的图片
            layer1_dir = os.path.join(task_dir, "第一层-最相关")
            os.makedirs(layer1_dir, exist_ok=True)
            
            self._emit_log("📥 第一层：下载原始Pin图片")
            
            # 获取高清原图
            img_elements = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "img[src*='pinimg.com']"
            )
            
            downloaded_l1 = 0
            seen_l1: Set[str] = set()
            for i, img_elem in enumerate(img_elements[:5]):  # 取前几个候选
                try:
                    src = img_elem.get_attribute("src") or ""
                    src = upgrade_image_url(src)
                    if src in seen_l1 or not src:
                        continue
                    seen_l1.add(src)
                    if self.downloader.download_image(src, layer1_dir, f"L1_{i+1:03d}"):
                        downloaded_l1 += 1
                        if downloaded_l1 >= 1:
                            break  # 原始Pin只需下载1张
                except Exception:
                    continue
            
            self._emit_log(f"✅ 第一层完成，下载 {downloaded_l1} 张")
            
            # 第二层及以上
            if self.max_layers >= 2:
                self._process_extended_layers([{"img_url": "", "pin_url": url}], task_dir)
                
        except Exception as e:
            self._emit_log(f"❌ 链接任务失败: {e}", "ERROR")
    
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
