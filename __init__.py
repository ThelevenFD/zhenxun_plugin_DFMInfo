import traceback
from json import loads

import httpx
from nonebot.adapters.onebot.v11 import Bot, Event
from nonebot.plugin import PluginMetadata
from nonebot_plugin_alconna import Alconna, on_alconna

from zhenxun.configs.config import BotConfig
from zhenxun.configs.utils import PluginExtraData
from zhenxun.services.log import logger
from zhenxun.utils.message import MessageUtils

__plugin_meta__ = PluginMetadata(
    name="三角洲小助手",
    description=f"{BotConfig.self_nickname}帮你获取三角洲信息！(数据来源：https://www.kkrb.net/)",
    usage="""
    指令：
    粥/洲
    """.strip(),
    extra=PluginExtraData(author="The_elevenFD", version="0.1").to_dict(),
)

urls = ["https://www.kkrb.net/getMenu", "https://www.kkrb.net/getOVData"]
maps = ["db", "cgxg", "bks", "htjd", "cxjy"]
works = ["tech", "workbench", "pharmacy", "armory"]
keys = []
msg_list = []

items = {}
headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.3351.109",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "sec-ch-ua-platform": '"Linux"',
    "X-Requested-With": "XMLHttpRequest",
    "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Microsoft Edge";v="138"',
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "sec-ch-ua-mobile": "?0",
    "Origin": "https://www.kkrb.net",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Referer": "https://www.kkrb.net/?viewpage=view%2Foverview",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
data = {}

matcher = on_alconna(Alconna("re:(洲|粥)"), priority=1, block=True)


def gen_list(event, content):
    base_msg = {
        "type": "node",
        "data": {"name": "真寻", "uin": event.self_id, "content": content},
        "summary": "咕咕嘎嘎!",
    }
    msg_list.append(base_msg)
    return msg_list


def get_cookie():
    try:
        del headers["Cookie"]
    except:
        pass
    global php_cookie, ver_cookie
    ck_response = httpx.post(url=urls[0], data=data, headers=headers, timeout=1)
    Menu_data = loads(ck_response.text)
    php_cookie = ck_response.headers["Set-Cookie"].split(";")[0]  # ["PHPSESSID"]
    ver_cookie = Menu_data["built_ver"]


get_cookie()


@matcher.handle()
async def get_data(bot: Bot, event: Event):
    try:
        headers["Cookie"] = php_cookie
        data["version"] = ver_cookie
        data_response = httpx.post(
            url=urls[1], data=data, headers=headers, timeout=1
        ).text
        data_dict = loads(data_response)
        item_info = data_dict["data"]["spData"]
        logger.info("获取三角洲信息!")
        for i in range(len(maps)):
            keys.append(data_dict["data"]["bdData"][maps[i]]["password"])
        for i in range(len(works)):
            items[item_info[works[i]]["itemName"]] = item_info[works[i]]["profit"]
        Itemname = list(items.keys())
        gen_list(
            event,
            f"零号大坝:{keys[0]}\n长弓溪谷:{keys[1]}\n巴克什:{keys[2]}\n航天基地:{keys[3]}\n潮汐监狱:{keys[4]}",
        )
        gen_list(
            event,
            f"特勤处制作产物推荐:\n技术中心:{Itemname[0]}\n当前利润:{int(items[Itemname[0]])}\n工作台:{Itemname[1]}\n当前利润:{int(items[Itemname[1]])}\n制药台:{Itemname[2]}\n当前利润:{int(items[Itemname[2]])}\n防具台:{Itemname[3]}\n当前利润:{int(items[Itemname[3]])}",
        )
        try:
            if event.group_id:
                await bot.send_group_forward_msg(
                    group_id=event.group_id, messages=msg_list
                )
        except AttributeError:
            await bot.send_private_forward_msg(user_id=event.user_id, messages=msg_list)
        except Exception as e:
            logger.error("出错了", e=e)
            await MessageUtils.build_message(f"合并转发信息错误:{e}...请重试...").send()
    except Exception as e:
        get_cookie()
        logger.error(f"出错了{traceback.format_exc()}", e=e)
        await MessageUtils.build_message("没有获取到数据...请重试...").send()
    finally:
        msg_list.clear()
        keys.clear()
        items.clear()
