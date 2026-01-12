import asyncio
import traceback
from typing import Any

from httpx import AsyncClient, HTTPError
from nonebot import get_driver
from nonebot.adapters.onebot.v11 import Bot, Event, Message
from nonebot.plugin import PluginMetadata
from nonebot_plugin_alconna import Alconna, on_alconna

# 假设这些是项目内的固有依赖
from zhenxun.configs.config import BotConfig
from zhenxun.configs.utils import PluginExtraData
from zhenxun.services.log import logger
from zhenxun.utils.message import MessageUtils

# --- 常量定义 ---
API_BASE = "https://www.kkrb.net"
URLS = {
    "MENU": f"{API_BASE}/getMenu",
    "OVERVIEW": f"{API_BASE}/getOVData",
    "HOME": f"{API_BASE}/?viewpage=view%2Foverview",
    "CPV": f"{API_BASE}/getCPVData",
}

# 战备值映射 (等级 -> 目标金额)
COST_MAPPING = {0: 112500, 1: 187500, 2: 550000, 3: 600000, 4: 780000}

# 地图代号映射
MAP_NAMES = {
    "db": "零号大坝",
    "cgxg": "长弓溪谷",
    "bks": "巴克什",
    "htjd": "航天基地",
    "cxjy": "潮汐监狱",
}

# 工作台类型映射
WORKSHOP_NAMES = {
    "tech": "技术中心",
    "workbench": "工作台",
    "pharmacy": "制药台",
    "armory": "防具台",
}

# 请求头
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": URLS["HOME"],
    "X-Requested-With": "XMLHttpRequest",
}

# --- 插件元数据 ---
__plugin_meta__ = PluginMetadata(
    name="三角洲小助手",
    description=f"{BotConfig.self_nickname}帮你获取三角洲信息！",
    usage="指令：洲 / 粥",
    extra=PluginExtraData(author="The_elevenFD", version="0.2").to_dict(),
)

driver = get_driver()


class DeltaService:
    """处理三角洲数据的服务类"""

    def __init__(self):
        self.client: AsyncClient | None = None
        self.version_cookie: str = ""
        # 共享 Session，复用连接
        self.client = AsyncClient(headers=DEFAULT_HEADERS, timeout=10.0)

    async def _ensure_cookies(self, force_refresh: bool = False):
        """确保 Cookie 有效，必要时刷新"""
        if (
            not force_refresh
            and self.version_cookie
            and self.client.cookies.get("PHPSESSID")
        ):
            return

        logger.info("正在获取/刷新三角洲 Cookie...")
        try:
            # 1. 访问主页获取 PHPSESSID
            await self.client.get(URLS["HOME"])

            # 2. 获取版本号
            resp = await self.client.post(URLS["MENU"])
            data = resp.json()
            self.version_cookie = data.get("built_ver", "")

            if not self.version_cookie:
                raise ValueError("未获取到版本号")

            logger.info(f"Cookie刷新成功: Ver={self.version_cookie}")
        except Exception as e:
            logger.error(f"获取Cookie失败: {e}")
            raise

    async def get_game_data(self) -> dict[str, Any]:
        """并发获取所有游戏数据"""
        await self._ensure_cookies()

        form_data = {"version": self.version_cookie, "globalData": "false"}

        try:
            # 并发请求 API，提高速度
            ov_task = self.client.post(URLS["OVERVIEW"], data=form_data)
            cpv_task = self.client.post(URLS["CPV"], data=form_data)

            ov_resp, cpv_resp = await asyncio.gather(ov_task, cpv_task)

            # 检查响应状态 (如果 Session 过期可能返回特定错误，这里简单处理)
            if ov_resp.status_code != 200 or cpv_resp.status_code != 200:
                raise HTTPError("API请求返回非200状态")

            return {
                "overview": ov_resp.json().get("data", {}),
                "cpv": cpv_resp.json().get("data", []),
            }
        except Exception:
            # 如果请求失败，尝试刷新 Cookie 后再试一次（简单的重试机制）
            logger.warning("数据请求失败，尝试刷新Cookie重试...")
            await self._ensure_cookies(force_refresh=True)
            # 更新 form_data 的 version
            form_data["version"] = self.version_cookie

            ov_resp = await self.client.post(URLS["OVERVIEW"], data=form_data)
            cpv_resp = await self.client.post(URLS["CPV"], data=form_data)

            return {
                "overview": ov_resp.json().get("data", {}),
                "cpv": cpv_resp.json().get("data", []),
            }

    def process_schemes(self, cpv_data: list[dict]) -> str:
        """处理战备方案数据"""
        # 预处理：将 market 类型的方案转为字典 {targetValue: scheme} 以便快速查找
        market_schemes = {
            s["targetValue"]: s for s in cpv_data if s.get("schemeType") == "market"
        }

        lines = ["凑战备方案:"]
        for level in range(5):
            target_cost = COST_MAPPING.get(level)
            scheme = market_schemes.get(target_cost)

            if scheme:
                items = [item["objectName"] for item in scheme.get("schemeItems", [])]
                item_str = "\n".join(items)
                cost = scheme.get("totalHafCost", "未知")
                lines.append(f"--- {target_cost} 档 ---\n{item_str}\n成本: {cost}")
            else:
                lines.append(f"--- {target_cost} 档 ---\n暂无方案")

        return "\n".join(lines)

    def process_passwords(self, bd_data: dict) -> str:
        """处理地图密码"""
        lines = []
        for code, name in MAP_NAMES.items():
            pwd = bd_data.get(code, {}).get("password", "未知")
            lines.append(f"{name}: {pwd}")
        return "\n".join(lines)

    def process_profits(self, sp_data: dict) -> str:
        """处理特勤处利润"""
        lines = ["特勤处制作产物推荐:"]
        for code, name in WORKSHOP_NAMES.items():
            info = sp_data.get(code, {})
            item_name = info.get("itemName", "未知")
            profit = int(info.get("profit", 0))
            lines.append(f"{name}: {item_name}\n当前利润: {profit}")
        return "\n".join(lines)

    async def close(self):
        if self.client:
            await self.client.aclose()


# 实例化服务
delta_service = DeltaService()


@driver.on_startup
async def _():
    # 预加载 Cookie
    try:
        await delta_service._ensure_cookies()
    except Exception:
        pass


@driver.on_shutdown
async def _():
    await delta_service.close()


# 指令处理器
command_matcher = on_alconna(Alconna("re:(洲|粥)"), priority=1, block=True)


@command_matcher.handle()
async def handle_delta_command(bot: Bot, event: Event):
    try:
        # 1. 获取数据
        data = await delta_service.get_game_data()

        overview = data["overview"]
        cpv_data = data["cpv"]

        # 2. 构建消息节点
        nodes = []

        # 辅助函数：创建节点
        def add_node(content: str):
            nodes.append(
                {
                    "type": "node",
                    "data": {"name": "真寻", "uin": event.self_id, "content": content},
                }
            )

        # 2.1 地图密码
        pw_msg = delta_service.process_passwords(overview.get("bdData", {}))
        add_node(pw_msg)

        # 2.2 制作产物
        profit_msg = delta_service.process_profits(overview.get("spData", {}))
        add_node(profit_msg)

        # 2.3 战备方案 (拆分为单条太长，这里合并为一个节点发送，或者按原逻辑拆分)
        # 原逻辑是每档一个节点，这里为了清晰，建议合并。
        # 如果坚持要分开，可以循环调用 add_node

        # 这里优化：只生成文本，不直接发，逻辑更清晰
        # 预处理 CPV 数据
        market_schemes = {
            s["targetValue"]: s for s in cpv_data if s.get("schemeType") == "market"
        }

        add_node("凑战备方案:")
        for level in range(5):
            target_cost = COST_MAPPING[level]
            scheme = market_schemes.get(target_cost)
            if scheme:
                items = "\n".join(
                    [i["objectName"] for i in scheme.get("schemeItems", [])]
                )
                msg = f"{target_cost}:\n{items}\n成本:{scheme['totalHafCost']}"
                add_node(msg)

        # 2.4 版权声明
        add_node("数据来源于: KK日报 & 官方\n若有侵权请联系删除")

        # 3. 发送合并转发
        if isinstance(event, Event):  # 简单的类型检查
            if getattr(event, "group_id", None):
                await bot.send_group_forward_msg(
                    group_id=event.group_id, messages=nodes
                )
            else:
                await bot.send_private_forward_msg(
                    user_id=event.user_id, messages=nodes
                )

    except Exception:
        logger.error(f"三角洲插件出错: {traceback.format_exc()}")
        await MessageUtils.build_message("获取数据失败，请稍后再试...").send()
