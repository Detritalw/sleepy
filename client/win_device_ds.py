# coding: utf-8
"""
win_device_ds.py
Windows 客户端用于上报设备状态到 Sleepy Web 应用
支持窗口标题检测、媒体播放信息、电池状态和鼠标空闲检测
- by DeepSeek -
- Original: win_device.py -
"""

import sys
import io
import asyncio
import time
from datetime import datetime
from typing import Tuple
import httpx
import threading
import win32api
import win32con
import win32gui
from pywintypes import error as pywinerror

# ----- 配置部分 -----

# 服务端配置
SERVER_URL = "http://localhost:9010"  # 服务端地址，末尾不带斜杠
SECRET = "wyf9test"  # 与服务端一致的密钥

# 设备配置
DEVICE_ID = "device-1"  # 设备标识符（唯一）
DEVICE_SHOW_NAME = "MyDevice1"  # 显示名称

# 媒体设备配置（如果启用独立媒体设备）
MEDIA_DEVICE_ID = "media-device"
MEDIA_DEVICE_SHOW_NAME = "正在播放"

# 检测配置
CHECK_INTERVAL = 5  # 检查间隔（秒）
MOUSE_IDLE_TIME = 15  # 鼠标静止判定时间（分钟）
MOUSE_MOVE_THRESHOLD = 10  # 鼠标移动检测的最小距离（像素）

# 功能开关
BYPASS_SAME_REQUEST = True  # 是否忽略重复请求
REVERSE_APP_NAME = False  # 是否反转窗口标题
MEDIA_INFO_ENABLED = True  # 是否启用媒体信息获取
MEDIA_INFO_MODE = "standalone"  # 媒体信息显示模式: 'prefix' 或 'standalone'
BATTERY_INFO_ENABLED = True  # 是否启用电源状态获取

# 过滤列表
SKIPPED_NAMES = [  # 跳过更新的窗口标题
    "",  # 空字符串
    "系统托盘溢出窗口。", "新通知", "任务切换", "快速设置", "通知中心",
    "操作中心", "日期和时间信息", "网络连接", "电池信息", "搜索",
    "任务视图", "任务切换", "Program Manager", "贴靠助手",  # 桌面组件
    "Flow.Launcher", "Snipper - Snipaste", "Paster - Snipaste"  # 其他程序
]

NOT_USING_NAMES = [  # 视为未在使用的窗口标题
    "启动", "「开始」菜单",  # 开始菜单
    "我们喜欢这张图片，因此我们将它与你共享。", "就像你看到的图像一样？选择以下选项",
    "喜欢这张图片吗?", "Windows 默认锁屏界面"  # 锁屏界面
]

# 其他配置
ENCODING = "gb18030"  # 控制台输出编码
PROXY = ""  # 代理地址，空字符串表示禁用
DEBUG = False  # 是否显示调试信息

# ----- 初始化 -----

# 设置控制台编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding=ENCODING)

# 全局状态变量
last_window = ""
last_mouse_pos = win32api.GetCursorPos()
last_mouse_move_time = time.time()
is_mouse_idle = False
cached_window_title = ""
last_media_playing = False
last_media_content = ""

# ----- 工具函数 -----


def log(msg: str, **kwargs):
    """带时间戳的日志输出"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cleaned_msg = str(msg).replace("\u200b", "")
    print(f"[{timestamp}] {cleaned_msg}", flush=True, **kwargs)


def debug(msg: str, **kwargs):
    """调试日志输出"""
    if DEBUG:
        log(msg, **kwargs)


def reverse_app_name(name: str) -> str:
    """反转应用名称（将末尾的应用名提前）"""
    if " - " not in name:
        return name

    parts = name.split(" - ")
    return " - ".join(reversed(parts))

# ----- API 客户端 -----


class SleepyAPIClient:
    """Sleepy API 客户端"""

    def __init__(self, base_url: str, secret: str, proxy: str = ""):
        self.base_url = base_url.rstrip("/")
        self.secret = secret
        self.proxy = proxy if proxy else None
        self.timeout = 7.5

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """发送 HTTP 请求"""
        url = f"{self.base_url}{endpoint}"

        # 添加鉴权信息
        if "json" in kwargs and isinstance(kwargs["json"], dict):
            kwargs["json"]["secret"] = self.secret
        else:
            kwargs["params"] = kwargs.get("params", {})
            kwargs["params"]["secret"] = self.secret

        # 设置请求头
        headers = kwargs.get("headers", {})
        headers["Content-Type"] = "application/json"
        kwargs["headers"] = headers

        # 发送请求
        async with httpx.AsyncClient(proxy=self.proxy, timeout=self.timeout) as client:
            if method.lower() == "get":
                return await client.get(url, **kwargs)
            elif method.lower() == "post":
                return await client.post(url, **kwargs)
            else:
                raise ValueError(f"不支持的 HTTP 方法: {method}")

    async def set_device_status(
        self,
        device_id: str,
        show_name: str,
        using: bool,
        status: str,
        **fields
    ) -> httpx.Response:
        """设置设备状态"""
        data = {
            "id": device_id,
            "show_name": show_name,
            "using": using,
            "status": status,
            "fields": fields
        }

        return await self._make_request("POST", "/api/device/set", json=data)

    async def remove_device(self, device_id: str) -> httpx.Response:
        """移除设备"""
        return await self._make_request("GET", f"/api/device/remove?id={device_id}")

    async def clear_devices(self) -> httpx.Response:
        """清除所有设备"""
        return await self._make_request("GET", "/api/device/clear")

    async def query_status(self, include_meta: bool = False, include_metrics: bool = False) -> httpx.Response:
        """查询状态"""
        params = {}
        if include_meta:
            params["meta"] = "true"
        if include_metrics:
            params["metrics"] = "true"

        return await self._make_request("GET", "/api/status/query", params=params)

    async def set_global_status(self, status_id: int) -> httpx.Response:
        """设置全局状态"""
        return await self._make_request("GET", f"/api/status/set?status={status_id}")

    async def get_status_list(self) -> httpx.Response:
        """获取状态列表"""
        return await self._make_request("GET", "/api/status/list")

    async def get_metrics(self) -> httpx.Response:
        """获取统计信息"""
        return await self._make_request("GET", "/api/metrics")

# ----- 系统信息获取 -----


async def get_media_info() -> Tuple[bool, str, str, str]:
    """获取 Windows 媒体播放信息"""
    if not MEDIA_INFO_ENABLED:
        return False, "", "", ""

    try:
        # 动态导入媒体控制模块
        if sys.version_info >= (3, 10):
            import winrt.windows.media.control as media
        else:
            import winrt.windows.media.control as media

        # 获取媒体会话管理器
        manager = await media.GlobalSystemMediaTransportControlsSessionManager.request_async()
        session = manager.get_current_session()

        if not session:
            return False, "", "", ""

        # 获取播放状态
        info = session.get_playback_info()
        is_playing = info.playback_status == media.GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING

        # 获取媒体属性
        props = await session.try_get_media_properties_async()

        title = props.title or "" if props else ""
        artist = props.artist or "" if props else ""
        album = props.album_title or "" if props else ""

        # 过滤无效专辑名
        if "未知唱片集" in album or ("<" in album and ">" in album):
            album = ""

        debug(f"媒体信息: 播放中={is_playing}, 标题='{title}', 艺术家='{artist}', 专辑='{album}'")
        return is_playing, title, artist, album

    except Exception as e:
        debug(f"获取媒体信息失败: {e}")
        return False, "", "", ""


def get_battery_info() -> Tuple[float, str]:
    """获取电池信息"""
    if not BATTERY_INFO_ENABLED:
        return 0, "未知"

    try:
        import psutil
        battery = psutil.sensors_battery()

        if battery is None:
            return 0, "未知"

        percent = battery.percent
        power_plugged = battery.power_plugged
        status = "⚡" if power_plugged else ""

        debug(f"电池信息: {percent}%, 状态: {status}")
        return percent, status

    except Exception as e:
        debug(f"获取电池信息失败: {e}")
        return 0, "未知"


def check_mouse_idle() -> bool:
    """检查鼠标是否静止"""
    global last_mouse_pos, last_mouse_move_time, is_mouse_idle

    try:
        current_pos = win32api.GetCursorPos()
    except pywinerror as e:
        debug(f"获取鼠标位置失败: {e}")
        return is_mouse_idle

    current_time = time.time()

    # 计算鼠标移动距离
    dx = current_pos[0] - last_mouse_pos[0]
    dy = current_pos[1] - last_mouse_pos[1]
    distance_sq = dx * dx + dy * dy

    # 检查是否超过移动阈值
    if distance_sq > MOUSE_MOVE_THRESHOLD * MOUSE_MOVE_THRESHOLD:
        last_mouse_pos = current_pos
        last_mouse_move_time = current_time

        if is_mouse_idle:
            is_mouse_idle = False
            distance = distance_sq ** 0.5
            log(f"鼠标唤醒: 移动了 {distance:.1f}px > {MOUSE_MOVE_THRESHOLD}px")
        else:
            debug(f"鼠标移动: {distance_sq**0.5:.1f}px > {MOUSE_MOVE_THRESHOLD}px")

        return False

    # 检查是否超过静止时间
    idle_time = current_time - last_mouse_move_time
    debug(f"鼠标空闲时间: {idle_time:.1f}s / {MOUSE_IDLE_TIME*60:.1f}s")

    if idle_time > MOUSE_IDLE_TIME * 60:
        if not is_mouse_idle:
            is_mouse_idle = True
            log(f"鼠标进入空闲状态: {idle_time/60:.1f} 分钟无活动")
        return True

    return is_mouse_idle


def get_window_title() -> str:
    """获取当前窗口标题"""
    try:
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)

        if REVERSE_APP_NAME and " - " in title:
            title = reverse_app_name(title)

        return title
    except Exception as e:
        debug(f"获取窗口标题失败: {e}")
        return ""

# ----- 关机处理 -----


def on_shutdown(hwnd, msg, wparam, lparam):
    """系统关机事件处理"""
    if msg == win32con.WM_QUERYENDSESSION:
        log("接收到关机事件，发送未使用状态...")

        try:
            # 在新的事件循环中运行异步函数
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            client = SleepyAPIClient(SERVER_URL, SECRET, PROXY)
            resp = loop.run_until_complete(
                client.set_device_status(
                    DEVICE_ID, DEVICE_SHOW_NAME, False, "要关机了喵"
                )
            )

            loop.close()

            if resp.status_code == 200:
                log("关机状态发送成功")
            else:
                log(f"关机状态发送失败: {resp.status_code} - {resp.text}")

        except Exception as e:
            log(f"关机状态发送异常: {e}")

        return True  # 允许关机或注销

    return 0  # 其他消息


def setup_shutdown_listener():
    """设置关机事件监听器"""
    try:
        # 注册窗口类
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = on_shutdown
        wc.lpszClassName = "ShutdownListener"
        wc.hInstance = win32api.GetModuleHandle(None)

        # 注册窗口类
        class_atom = win32gui.RegisterClass(wc)

        # 创建窗口
        hwnd = win32gui.CreateWindow(
            class_atom, "Sleepy Shutdown Listener", 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None
        )

        # 启动消息循环线程
        def message_loop():
            win32gui.PumpMessages()

        message_thread = threading.Thread(target=message_loop, daemon=True)
        message_thread.start()

        log("关机事件监听器已启动")
    except Exception as e:
        log(f"设置关机事件监听器失败: {e}")

# ----- 主逻辑 -----


async def update_device_status(client: SleepyAPIClient):
    """更新设备状态"""
    global last_window, cached_window_title, is_mouse_idle
    global last_media_playing, last_media_content

    # 获取当前窗口标题和鼠标状态
    window_title = get_window_title()
    mouse_idle = check_mouse_idle()
    debug(f"窗口: '{window_title}', 鼠标空闲: {mouse_idle}")

    # 处理鼠标空闲状态
    if mouse_idle:
        if not is_mouse_idle:  # 刚进入空闲状态
            cached_window_title = window_title
            log("进入空闲状态，缓存窗口标题")
        is_mouse_idle = True
        using = False
        display_title = ""
    else:
        if is_mouse_idle:  # 刚从空闲状态恢复
            window_title = cached_window_title
            log("退出空闲状态，恢复窗口标题")
        is_mouse_idle = False
        using = True
        display_title = window_title

    # 添加电池信息
    if BATTERY_INFO_ENABLED and using and display_title:
        battery_percent, battery_status = get_battery_info()
        if battery_percent > 0:
            display_title = f"[🔋{battery_percent}%{battery_status}] {display_title}"

    # 检查是否需要跳过更新
    if window_title in SKIPPED_NAMES:
        if mouse_idle == is_mouse_idle:  # 鼠标状态未改变
            debug(f"跳过窗口: '{window_title}' (在跳过列表中)")
            return
        else:  # 鼠标状态改变，使用上次的窗口标题
            debug(f"跳过窗口但鼠标状态改变: '{window_title}', 使用上次标题: '{last_window}'")
            display_title = last_window

    # 检查是否视为未在使用
    if window_title in NOT_USING_NAMES:
        using = False
        debug(f"标记为未使用: '{window_title}' (在未使用列表中)")

    # 检查是否需要发送更新
    should_update = (
        not BYPASS_SAME_REQUEST or
        mouse_idle != is_mouse_idle or
        display_title != last_window
    )

    if not should_update:
        debug("状态未改变，跳过更新")
        return

    # 发送设备状态更新
    try:
        log(f"发送状态: 使用中={using}, 状态='{display_title}'")
        resp = await client.set_device_status(
            DEVICE_ID, DEVICE_SHOW_NAME, using, display_title
        )

        if resp.status_code == 200:
            last_window = display_title
            debug("状态更新成功")
        else:
            log(f"状态更新失败: {resp.status_code} - {resp.text}")
    except Exception as e:
        log(f"状态更新异常: {e}")


async def update_media_status(client: SleepyAPIClient):
    """更新媒体播放状态"""
    global last_media_playing, last_media_content

    if not MEDIA_INFO_ENABLED or MEDIA_INFO_MODE != "standalone":
        return

    # 获取媒体信息
    is_playing, title, artist, album = await get_media_info()

    # 格式化媒体信息
    media_content = ""
    if is_playing and (title or artist):
        parts = []
        if title:
            parts.append(f"♪{title}")
        if artist and artist != title:
            parts.append(artist)
        if album and album != title and album != artist:
            parts.append(album)
        media_content = " - ".join(parts) if parts else "♪播放中"

    # 检查媒体状态是否改变
    media_changed = (
        is_playing != last_media_playing or
        (is_playing and media_content != last_media_content)
    )

    if not media_changed:
        debug("媒体状态未改变，跳过更新")
        return

    # 发送媒体状态更新
    try:
        if is_playing:
            log(f"发送媒体状态: 播放中, 内容='{media_content}'")
            resp = await client.set_device_status(
                MEDIA_DEVICE_ID, MEDIA_DEVICE_SHOW_NAME, True, media_content
            )
        else:
            log("发送媒体状态: 未播放")
            resp = await client.set_device_status(
                MEDIA_DEVICE_ID, MEDIA_DEVICE_SHOW_NAME, False, "没有媒体播放"
            )

        if resp.status_code == 200:
            last_media_playing = is_playing
            last_media_content = media_content
            debug("媒体状态更新成功")
        else:
            log(f"媒体状态更新失败: {resp.status_code} - {resp.text}")
    except Exception as e:
        log(f"媒体状态更新异常: {e}")


async def main_loop():
    """主循环"""
    client = SleepyAPIClient(SERVER_URL, SECRET, PROXY)

    log(f"启动 Sleepy 客户端，设备: {DEVICE_SHOW_NAME} ({DEVICE_ID})")
    log(f"服务器: {SERVER_URL}")
    log(f"检查间隔: {CHECK_INTERVAL} 秒")

    if MEDIA_INFO_ENABLED:
        log(f"媒体信息: 已启用, 模式: {MEDIA_INFO_MODE}")

    if BATTERY_INFO_ENABLED:
        log("电池信息: 已启用")

    # 设置关机监听
    setup_shutdown_listener()

    try:
        while True:
            await update_device_status(client)
            await update_media_status(client)
            await asyncio.sleep(CHECK_INTERVAL)
    except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
        log("接收到中断信号，正在关闭...")

        # 发送未使用状态
        try:
            log("发送最终未使用状态...")
            resp = await client.set_device_status(
                DEVICE_ID, DEVICE_SHOW_NAME, False, "未在使用"
            )

            if MEDIA_INFO_ENABLED and MEDIA_INFO_MODE == "standalone":
                await client.set_device_status(
                    MEDIA_DEVICE_ID, MEDIA_DEVICE_SHOW_NAME, False, "未在使用"
                )

            if resp.status_code == 200:
                log("最终状态发送成功")
            else:
                log(f"最终状态发送失败: {resp.status_code} - {resp.text}")
        except Exception as e:
            log(f"最终状态发送异常: {e}")
    finally:
        log("客户端已关闭")

# ----- 入口点 -----

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except Exception as e:
        log(f"客户端异常退出: {e}")
        input("按 Enter 键退出...")
