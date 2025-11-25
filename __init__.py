# -*- coding: utf-8 -*-
"""
三角洲小助手插件
功能：获取三角洲游戏的相关信息，包括地图密码、战备方案、制作产物推荐等
作者：The_elevenFD
版本：0.1
"""

import traceback
from json import loads
from typing import Optional

from httpx import AsyncClient
from nonebot.adapters.onebot.v11 import Bot, Event
from nonebot.plugin import PluginMetadata
from nonebot_plugin_alconna import Alconna, on_alconna
from nonebot import get_driver

from zhenxun.configs.config import BotConfig
from zhenxun.configs.utils import PluginExtraData
from zhenxun.services.log import logger
from zhenxun.utils.message import MessageUtils

# 插件元数据定义
__plugin_meta__ = PluginMetadata(
    name="三角洲小助手",
    description=f"{BotConfig.self_nickname}帮你获取三角洲信息！",
    usage="""
    指令：
        粥
    """.strip(),
    extra=PluginExtraData(author="The_elevenFD", version="0.1").to_dict(),
)

# 获取驱动实例
driver = get_driver()

# API接口URL列表
api_urls = [
    "https://www.kkrb.net/getMenu",        # 获取菜单数据
    "https://www.kkrb.net/getOVData",       # 获取概览数据
    "https://www.kkrb.net/?viewpage=view%2Foverview",  # 主页URL
    "https://www.kkrb.net/getCPVData"      # 获取CPV数据
]

# 地图名称映射
map_codes = ["db", "cgxg", "bks", "htjd", "cxjy"]  # 对应：零号大坝、长弓溪谷、巴克什、航天基地、潮汐监狱

# 工作台类型
workshop_types = ["tech", "workbench", "pharmacy", "armory"]  # 对应：技术中心、工作台、制药台、防具台

# 请求头信息
session_cookies = {}
request_headers = {
    "sec-ch-ua-platform": "\"Windows\"",
    "x-requested-with": "XMLHttpRequest",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
    "accept": "*/*",
    "sec-ch-ua": "\"Microsoft Edge\";v=\"143\", \"Chromium\";v=\"143\", \"Not A(Brand\";v=\"24\"",
    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    "sec-ch-ua-mobile": "?0",
    "origin": "https://www.kkrb.net",
    "sec-fetch-site": "same-origin",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
    "referer": "https://www.kkrb.net/?viewpage=view%2Foverview",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "priority": "u=1, i"
}

# 请求数据
request_data = ""

# Cookie缓存
cookie_cache = {
    "php_session_id": "",   # PHPSESSID
    "version_cookie": "",   # 版本Cookie
}

# 创建指令匹配器，匹配"洲"或"粥"
command_matcher = on_alconna(Alconna("re:(洲|粥)"), priority=1, block=True)


async def generate_forward_message(event, content, insert: Optional[int] = None, message_list: list = []):
    """
    生成转发消息节点
    
    Args:
        event: 事件对象
        content: 消息内容
        insert: 插入位置，None表示追加到末尾
        message_list: 消息列表
    
    Returns:
        list: 更新后的消息列表
    """
    base_message = {
        "type": "node",
        "data": {"name": "真寻", "uin": event.self_id, "content": content},
        "summary": "咕咕嘎嘎!",
        "prompt": "咕咕嘎嘎!",
    }
    if insert is not None:
        message_list.insert(insert, base_message)
    else:
        message_list.append(base_message)
    return message_list


async def fetch_cookies():
    """
    获取网站Cookie
    
    Returns:
        tuple: (php_session_id, version_cookie) Cookie字符串
    """
    try:
        async with AsyncClient() as http_client:
            # 访问主页获取PHPSESSID
            home_response = await http_client.get(api_urls[2], headers=request_headers, cookies=session_cookies, timeout=3)
            php_session_id = dict(home_response.cookies).get("PHPSESSID","")
            cookie_cache["php_session_id"] = php_session_id
            session_cookies["PHPSESSID"] = php_session_id 
            
            # 获取菜单数据，提取版本Cookie
            menu_response = await http_client.post(api_urls[0], headers=request_headers, cookies=session_cookies, timeout=3)
            menu_data = loads(menu_response.text)
            version_cookie = menu_data["built_ver"]
            cookie_cache["version_cookie"] = version_cookie
            return php_session_id, version_cookie
    except Exception:
        logger.error(traceback.format_exc())
        return "",""


@command_matcher.handle()
async def handle_delta_command(bot: Bot, event: Event, retry_count: int = 0):
    """
    处理"洲/粥"指令，获取三角洲信息
    
    Args:
        bot: 机器人实例
        event: 事件对象
        retry_count: 重试次数，默认0
    """
    forward_messages = []  # 转发消息列表
    map_passwords = []     # 地图密码列表
    item_profits = {}      # 物品利润字典
    
    # 重试次数限制
    if retry_count > 3:
        await MessageUtils.build_message("获取数据失败...请重试...").send()
        return
    
    try:
        async with AsyncClient() as http_client:
            # 构建请求数据
            request_data = f"version={cookie_cache['version_cookie']}&globalData=false"
            logger.error(f"query:{request_data}")
            
            # 获取概览数据
            overview_response = await http_client.post(
                url=api_urls[1], data=request_data, headers=request_headers, cookies=session_cookies, timeout=1
            )
            
            # 获取CPV数据（战备方案数据）
            cpv_response = await http_client.post(
                url=api_urls[3], data=request_data, headers=request_headers, cookies=session_cookies, timeout=1
            )
            
            logger.info("获取CPV信息!")
            cpv_data_dict = loads(cpv_response.text)
            cpv_info = cpv_data_dict["data"]  # CPV数据
            
            logger.info("获取三角洲信息!")
            overview_data_dict = loads(overview_response.text)
            special_forces_data = overview_data_dict["data"]["spData"]  # 特勤处数据
            
            # 卡战备方案处理
            schemes_by_cost = {}  # 按战备值分类的方案字典
            scheme_items_by_cost = {112500:"", 187500:"", 550000:"", 600000:"", 780000:""}  # 战备值对应的物品列表
            await generate_forward_message(event, "凑战备方案:", 2, forward_messages,)
            for cost_level in range(5):
                # 战备值映射：0-112500, 1-187500, 2-550000, 3-600000, 4-780000
                cost_mapping = {0:112500, 1:187500, 2:550000, 3:600000, 4:780000}
                
                # 查找对应战备值的市场方案
                for _, scheme in enumerate(cpv_info):
                    if scheme["targetValue"] == cost_mapping[cost_level] and scheme["schemeType"] == "market": 
                        schemes_by_cost[scheme["targetValue"]] = scheme
                        break
                
                # 提取方案中的物品名称
                for item_index in range(len(schemes_by_cost[cost_mapping[cost_level]]["schemeItems"])):
                    scheme_items_by_cost[cost_mapping[cost_level]] += "\n" + schemes_by_cost[cost_mapping[cost_level]]["schemeItems"][item_index]["objectName"]
                scheme_items_by_cost[cost_mapping[cost_level]] += "\n" + f"成本:{schemes_by_cost[cost_mapping[cost_level]]['totalHafCost']}"
                # 构建战备方案消息
                await generate_forward_message(
                    event,
                    f"{cost_mapping[cost_level]}:{scheme_items_by_cost[cost_mapping[cost_level]]}",
                    None,
                    forward_messages,
                )
                
            
            # 地图密码获取
            for map_index in range(len(map_codes)):
                map_passwords.append(overview_data_dict["data"]["bdData"][map_codes[map_index]]["password"])
            
            # 特勤处制作产物推荐
            for workshop_index in range(len(workshop_types)):
                item_profits[special_forces_data[workshop_types[workshop_index]]["itemName"]] = special_forces_data[workshop_types[workshop_index]]["profit"]
            
            item_names = list(item_profits.keys())
            
            # 添加地图密码消息
            await generate_forward_message(
                event,
                f"""零号大坝:{map_passwords[0]}
长弓溪谷:{map_passwords[1]}
巴克什:{map_passwords[2]}
航天基地:{map_passwords[3]}
潮汐监狱:{map_passwords[4]}""",
                0,
                forward_messages,
            )
            
            # 添加特勤处制作产物推荐消息
            await generate_forward_message(
                event,
                f"""特勤处制作产物推荐:
技术中心:{item_names[0]}
当前利润:{int(item_profits[item_names[0]])}
工作台:{item_names[1]}
当前利润:{int(item_profits[item_names[1]])}
制药台:{item_names[2]}
当前利润:{int(item_profits[item_names[2]])}
防具台:{item_names[3]}
当前利润:{int(item_profits[item_names[3]])}""",
                0,
                forward_messages,
            )
            await generate_forward_message(
                event,
                "数据来源于:KK日报&官方\n若有侵权请联系删除",
                None,
                forward_messages,
            )

            # 发送转发消息
            try:
                if event.group_id:
                    # 群聊转发
                    await bot.send_group_forward_msg(
                        group_id=event.group_id, messages=forward_messages
                    )
            except AttributeError:
                # 私聊转发
                await bot.send_private_forward_msg(user_id=event.user_id, messages=forward_messages)
            except Exception as error:
                logger.error("出错了", e=traceback.format_exc())
                await MessageUtils.build_message(f"合并转发信息错误:{error}...请重试...").send()
    except Exception:
        # 异常处理：重新获取Cookie并重试
        logger.error("出错了", e=traceback.format_exc())
        cookie_cache["php_session_id"], cookie_cache["version_cookie"] = await fetch_cookies()
        await handle_delta_command(bot, event, retry_count + 1)


@driver.on_startup
async def initialize_plugin():
    """
    插件启动时初始化Cookie
    """
    await fetch_cookies()
    logger.info(f"初始化cookie:{cookie_cache}")