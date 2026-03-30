import asyncio
from typing import Any

# 确保安装了 curl_cffi: pip install curl_cffi
from httpx import AsyncClient

from zhenxun.services.log import logger

API_BASE = "https://dfapi.eleven.icu"
URLS = {
    "OVERVIEW": f"{API_BASE}/getOVData",
    "CPV": f"{API_BASE}/getCPVData",
}

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
        pass

    async def get_game_data(self, retry: int = 0) -> dict[str, Any]:
        """并发获取所有游戏数据"""
        if retry > 3:
            logger.error("获取数据错误: 重试次数超限")
            return {}

        try:
            async with AsyncClient(
                timeout=15.0,
            ) as session:
                # 并发请求
                ov_task = session.get(URLS["OVERVIEW"])
                cpv_task = session.get(URLS["CPV"])

                ov_resp, cpv_resp = await asyncio.gather(ov_task, cpv_task)

                # 记录原始响应状态
                logger.info(f"API响应状态 - OVERVIEW: {ov_resp.status_code}, CPV: {cpv_resp.status_code}")

                # 解析 OVERVIEW 响应
                ov_data = {}
                if ov_resp.status_code == 200:
                    try:
                        ov_json = ov_resp.json()
                        
                        # 校验响应结构，避免静默吞掉上游契约变更
                        if not isinstance(ov_json, dict):
                            logger.warning(
                                f"意外的OVERVIEW响应结构: 期望dict, 实际得到 {type(ov_json).__name__}, 内容: {str(ov_json)[:200]}"
                            )
                        else:
                            # 新的数据结构: {"code": 1, "msg": "获取成功", "data": {...}}
                            if "data" in ov_json:
                                data = ov_json["data"]
                                if isinstance(data, dict):
                                    ov_data = data
                                    logger.info("OVERVIEW: 使用新的数据结构 (code/msg/data)")
                                else:
                                    logger.warning(f"OVERVIEW data字段不是dict: {type(data).__name__}")
                            else:
                                # 兼容旧结构: 直接返回数据
                                ov_data = ov_json
                                logger.info("OVERVIEW: 使用旧的数据结构 (直接返回数据)")
                    except Exception as e:
                        logger.warning(f"OVERVIEW JSON解析失败: {e}, 响应文本: {ov_resp.text[:200]}")
                else:
                    logger.warning(f"OVERVIEW API 返回错误状态码: {ov_resp.status_code}, 响应: {ov_resp.text[:200]}")
                
                # 解析 CPV 响应
                cpv_data = []
                if cpv_resp.status_code == 200:
                    try:
                        cpv_json = cpv_resp.json()
                        
                        # 校验响应结构，避免静默吞掉上游契约变更
                        if not isinstance(cpv_json, (dict, list)):
                            logger.warning(
                                f"意外的CPV响应结构: 期望dict或list, 实际得到 {type(cpv_json).__name__}, 内容: {str(cpv_json)[:200]}"
                            )
                        elif isinstance(cpv_json, dict):
                            # 新的数据结构: {"code": 1, "msg": "获取成功", "data": [...]}
                            if "data" in cpv_json:
                                data = cpv_json["data"]
                                if isinstance(data, list):
                                    cpv_data = data
                                    logger.info("CPV: 使用新的数据结构 (code/msg/data)")
                                else:
                                    logger.warning(f"CPV data字段不是list: {type(data).__name__}")
                            else:
                                logger.warning(f"CPV响应是dict但没有data字段: {list(cpv_json.keys())}")
                        elif isinstance(cpv_json, list):
                            # 兼容旧结构: 直接返回列表
                            cpv_data = cpv_json
                            logger.info("CPV: 使用旧的数据结构 (直接返回列表)")
                    except Exception as e:
                        logger.warning(f"CPV JSON解析失败: {e}, 响应文本: {cpv_resp.text[:200]}")
                else:
                    logger.warning(f"CPV API 返回错误状态码: {cpv_resp.status_code}, 响应: {cpv_resp.text[:200]}")

                # 记录最终获取的数据状态
                logger.info(f"数据获取结果 - overview keys: {list(ov_data.keys())}, cpv长度: {len(cpv_data)}")

                return {
                    "overview": ov_data if isinstance(ov_data, dict) else {},
                    "cpv": cpv_data if isinstance(cpv_data, list) else [],
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
