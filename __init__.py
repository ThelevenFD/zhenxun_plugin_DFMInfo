import traceback
from json import loads

from httpx import AsyncClient
from nonebot.adapters.onebot.v11 import Bot, Event
from nonebot.plugin import PluginMetadata
from nonebot_plugin_alconna import Alconna, on_alconna
from nonebot import get_driver

from zhenxun.configs.config import BotConfig
from zhenxun.configs.utils import PluginExtraData
from zhenxun.services.log import logger
from zhenxun.utils.message import MessageUtils

__plugin_meta__ = PluginMetadata(
    name="三角洲小助手",
    description=f"{BotConfig.self_nickname}帮你获取三角洲信息！",
    usage="""
    指令：
        粥
    """.strip(),
    extra=PluginExtraData(author="The_elevenFD", version="0.1").to_dict(),
)
driver = get_driver()
urls = ["https://www.kkrb.net/getMenu", "https://www.kkrb.net/getOVData","https://www.kkrb.net/?viewpage=view%2Foverview"]
maps = ["db", "cgxg", "bks", "htjd", "cxjy"]
works = ["tech", "workbench", "pharmacy", "armory"]

cookies = {}
headers = {
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
data = ""
cookie_cache = {
    "php_cookie": "",
    "ver_cookie": "",
}

matcher = on_alconna(Alconna("re:(洲|粥)"), priority=1, block=True)

async def gen_list(event, content, msg_list):
    base_msg = {
        "type": "node",
        "data": {"name": "真寻", "uin": event.self_id, "content": content},
        "summary": "咕咕嘎嘎!",
        "prompt": "咕咕嘎嘎!",
    }
    msg_list.append(base_msg)
    return msg_list


async def get_cookie():
    try:
        async with AsyncClient() as client:
            home_resp = await client.get(urls[2], headers=headers, cookies=cookies, timeout=3)
            php_cookie = dict(home_resp.cookies).get("PHPSESSID","")  # ["PHPSESSID"]
            cookie_cache["php_cookie"] = php_cookie
            cookies["PHPSESSID"] = php_cookie 
            menu_resp = await client.post(urls[0], headers=headers, cookies=cookies, timeout=3)
            Menu_data = loads(menu_resp.text)
            ver_cookie = Menu_data["built_ver"]
            cookie_cache["ver_cookie"] = ver_cookie
            return php_cookie, ver_cookie
    except Exception:
        logger.error(traceback.format_exc())
        return "",""


@matcher.handle()
async def get_data(bot: Bot, event: Event, retry: int = 0):
    msg_list = []
    keys = []
    items = {}
    if retry > 3:
        await MessageUtils.build_message("获取数据失败...请重试...").send()
        return
    try:
        async with AsyncClient() as client:
            data = f"version={cookie_cache['ver_cookie']}&globalData=false"
            logger.error(f"query:{data}")
            data_response = await client.post(
                url=urls[1], data=data, headers=headers, cookies=cookies, timeout=1
            )
            logger.error(data_response.text)
            data_dict = loads(data_response.text)
            item_info = data_dict["data"]["spData"]
            logger.info("获取三角洲信息!")
            for i in range(len(maps)):
                keys.append(data_dict["data"]["bdData"][maps[i]]["password"])
            for i in range(len(works)):
                items[item_info[works[i]]["itemName"]] = item_info[works[i]]["profit"]
            Itemname = list(items.keys())
            await gen_list(
                event,
                f"零号大坝:{keys[0]}\n长弓溪谷:{keys[1]}\n巴克什:{keys[2]}\n航天基地:{keys[3]}\n潮汐监狱:{keys[4]}",
                msg_list,
            )
            await gen_list(
                event,
                f"特勤处制作产物推荐:\n技术中心:{Itemname[0]}\n当前利润:{int(items[Itemname[0]])}\n工作台:{Itemname[1]}\n当前利润:{int(items[Itemname[1]])}\n制药台:{Itemname[2]}\n当前利润:{int(items[Itemname[2]])}\n防具台:{Itemname[3]}\n当前利润:{int(items[Itemname[3]])}",
                msg_list,
            )
            try:
                if event.group_id:
                    await bot.send_group_forward_msg(
                        group_id=event.group_id, messages=msg_list
                    )
            except AttributeError:
                await bot.send_private_forward_msg(user_id=event.user_id, messages=msg_list)
            except Exception as e:
                logger.error("出错了", e=traceback.format_exc())
                await MessageUtils.build_message(f"合并转发信息错误:{e}...请重试...").send()
    except Exception:
        logger.error("出错了", e=traceback.format_exc())
        cookie_cache["php_cookie"], cookie_cache["ver_cookie"] = await get_cookie()
        await get_data(bot, event, retry + 1)



@driver.on_startup
async def plugin_startup():
    """插件启动时初始化"""
    print("插件正在初始化...")
    # 在这里进行初始化操作
    await get_cookie()
    logger.info(f"初始化cookie:{cookie_cache}")
