import asyncio
from typing import Any

from httpx import AsyncClient

from zhenxun.services.log import logger

# -------------------------------------------------------
# 补回缺失的字典定义
# -------------------------------------------------------

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


class DeltaService:
    """处理三角洲数据的服务类"""

    def __init__(self):
        self.ov_json: dict[str, Any] = {}
        self.cpv_json: dict[str, Any] = {}
        self.status_json: dict[str, Any] = {}
        self.API_BASE = ["https://dfapi1.eleven.icu", "https://dfapi.eleven.icu"]

    def _get_urls(self, retry) -> dict[str, str]:
        index = retry % len(self.API_BASE)
        return {
            "STATUS": f"{self.API_BASE[index]}/status",
            "OVERVIEW": f"{self.API_BASE[index]}/getOVData",
            "CPV": f"{self.API_BASE[index]}/getCPVData",
        }

    async def get_game_data(self, retry: int = 0) -> dict[str, Any]:
        """并发获取所有游戏数据"""
        if retry >= 3:
            logger.error("获取数据错误: 重试次数超限")
            return {}

        try:
            async with AsyncClient(
                timeout=15.0,
            ) as session:
                # 并发请求
                ov_task = session.get(self._get_urls(retry)["OVERVIEW"])
                cpv_task = session.get(self._get_urls(retry)["CPV"])
                status_task = session.get(self._get_urls(retry)["STATUS"])

                ov_resp, cpv_resp, status_resp = await asyncio.gather(
                    ov_task, cpv_task, status_task, return_exceptions=True
                )

                # 解析响应
                try:
                    self.ov_json = ov_resp.json()
                except Exception:
                    logger.warning("解析ovdata失败")
                    pass
                try:
                    self.cpv_json = cpv_resp.json()
                except Exception:
                    logger.warning("解析cpvdata失败")
                    pass
                try:
                    self.status_json = status_resp.json()
                except Exception:
                    pass

                return {
                    "overview": self.ov_json.get("data", {}),
                    "cpv": self.cpv_json.get("data", {}),
                    "status": self.status_json if self.status_json else {},
                }

        except Exception as e:
            logger.warning(f"请求失败({e})，尝试刷新重试...({retry + 1}/3)")
            return await self.get_game_data(retry + 1)

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
