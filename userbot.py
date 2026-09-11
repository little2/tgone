"""Telegram 使用者帳號管理程式入口。"""

import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path
import random
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

from aiogram_bot_operator import AiogramBotOperator
from tgone_mysql import MySQLPool
from user_account_manager import UserAccountManager
from human_bot_operator import HumanBotOperator


API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)


async def catch_miwen():
    # Implement the catch functionality here
    pass

async def main_check_user() -> None:
    account_manager = UserAccountManager()
    config = account_manager.load_config()
    MySQLPool.configure(
        host=config.get("db_host", os.getenv("MYSQL_DB_HOST", "localhost")),
        user=config.get("db_user", os.getenv("MYSQL_DB_USER", "")),
        password=config.get("db_password", os.getenv("MYSQL_DB_PASSWORD", "")),
        database=config.get("db_name", os.getenv("MYSQL_DB_NAME", "")),
        port=int(config.get("db_port", os.getenv("MYSQL_DB_PORT", 3306))),
    )

   

    try:
        await account_manager.check_all_userbot(config)
        # await account_manager.rec_new_account(
        #     phone_number="+15809565862",
        #     pw2fa="z4422404",
        # )
        # await account_manager.check_phone("+573012688582")
        # await account_manager.check_phone("+6282127491912")
        # await account_manager.check_phone("+916295379623")

    finally:
        await MySQLPool.close()


async def main() -> None:
    account_manager = UserAccountManager()
    config = account_manager.load_config()
    MySQLPool.configure(
        host=config.get("db_host", os.getenv("MYSQL_DB_HOST", "localhost")),
        user=config.get("db_user", os.getenv("MYSQL_DB_USER", "")),
        password=config.get("db_password", os.getenv("MYSQL_DB_PASSWORD", "")),
        database=config.get("db_name", os.getenv("MYSQL_DB_NAME", "")),
        port=int(config.get("db_port", os.getenv("MYSQL_DB_PORT", 3306))),
    )

    # 此段内容来自 JSON；保留 JSON 的 null 写法并在 Python 中对应为 None。
    null = None
    # script= {"version":"1","script":{"script_id":"classmate_private_topic_3p_001","title":"同学间的私密经历闲聊","start_at":"2026-01-01T00:00:00+08:00"},"chat":{"chat_id":0,"message_thread_id":null},"participants":[{"actor_id":"linhao","name":"林浩","sender_type":"user","sender_id":1001},{"actor_id":"achen","name":"阿辰","sender_type":"user","sender_id":1002},{"actor_id":"zimo","name":"子墨","sender_type":"user","sender_id":1003}],"messages":[{"message_id":"m001","after_start":8,"actor_id":"linhao","reply_to":null,"typing_duration":2,"content":{"text":"问个私密的事","parse_mode":null}},{"message_id":"m002","after_start":13,"actor_id":"achen","reply_to":"m001","typing_duration":1,"content":{"text":"你说啊","parse_mode":null}},{"message_id":"m003","after_start":18,"actor_id":"zimo","reply_to":null,"typing_duration":1,"content":{"text":"突然这么严肃","parse_mode":null}},{"message_id":"m004","after_start":76,"actor_id":"linhao","reply_to":null,"typing_duration":2,"content":{"text":"跟同学亲密过吗","parse_mode":null}},{"message_id":"m005","after_start":82,"actor_id":"achen","reply_to":"m004","typing_duration":2,"content":{"text":"有过一点经历","parse_mode":null}},{"message_id":"m006","after_start":88,"actor_id":"zimo","reply_to":null,"typing_duration":2,"content":{"text":"我只谈过恋爱","parse_mode":null}},{"message_id":"m007","after_start":144,"actor_id":"linhao","reply_to":"m005","typing_duration":2,"content":{"text":"不会很尴尬吗","parse_mode":null}},{"message_id":"m008","after_start":151,"actor_id":"achen","reply_to":null,"typing_duration":2,"content":{"text":"当时关系很好","parse_mode":null}},{"message_id":"m009","after_start":158,"actor_id":"zimo","reply_to":null,"typing_duration":2,"content":{"text":"后来还联系？","parse_mode":null}},{"message_id":"m010","after_start":212,"actor_id":"linhao","reply_to":null,"typing_duration":1,"content":{"text":"我也好奇这个","parse_mode":null}},{"message_id":"m011","after_start":219,"actor_id":"achen","reply_to":"m009","typing_duration":2,"content":{"text":"现在还是朋友","parse_mode":null}},{"message_id":"m012","after_start":226,"actor_id":"zimo","reply_to":null,"typing_duration":2,"content":{"text":"那还挺自然","parse_mode":null}},{"message_id":"m013","after_start":280,"actor_id":"linhao","reply_to":null,"typing_duration":2,"content":{"text":"谁先提的啊","parse_mode":null}},{"message_id":"m014","after_start":287,"actor_id":"achen","reply_to":"m013","typing_duration":2,"content":{"text":"算是互相试探","parse_mode":null}},{"message_id":"m015","after_start":294,"actor_id":"zimo","reply_to":null,"typing_duration":1,"content":{"text":"懂了哈哈","parse_mode":null}},{"message_id":"m016","after_start":348,"actor_id":"linhao","reply_to":null,"typing_duration":2,"content":{"text":"之后见面尴尬不","parse_mode":null}},{"message_id":"m017","after_start":355,"actor_id":"achen","reply_to":"m016","typing_duration":2,"content":{"text":"前两天有一点","parse_mode":null}},{"message_id":"m018","after_start":362,"actor_id":"zimo","reply_to":null,"typing_duration":2,"content":{"text":"换我估计脸红","parse_mode":null}},{"message_id":"m019","after_start":416,"actor_id":"linhao","reply_to":null,"typing_duration":1,"content":{"text":"哈哈我也是","parse_mode":null}},{"message_id":"m020","after_start":423,"actor_id":"achen","reply_to":null,"typing_duration":2,"content":{"text":"后来就习惯了","parse_mode":null}},{"message_id":"m021","after_start":430,"actor_id":"zimo","reply_to":null,"typing_duration":2,"content":{"text":"主要得双方愿意","parse_mode":null}},{"message_id":"m022","after_start":484,"actor_id":"linhao","reply_to":"m021","typing_duration":1,"content":{"text":"这个肯定","parse_mode":null}},{"message_id":"m023","after_start":491,"actor_id":"achen","reply_to":null,"typing_duration":2,"content":{"text":"边界也得说清楚","parse_mode":null}},{"message_id":"m024","after_start":498,"actor_id":"zimo","reply_to":null,"typing_duration":2,"content":{"text":"不然朋友难做","parse_mode":null}},{"message_id":"m025","after_start":552,"actor_id":"linhao","reply_to":null,"typing_duration":2,"content":{"text":"大学这种多吗","parse_mode":null}},{"message_id":"m026","after_start":559,"actor_id":"achen","reply_to":"m025","typing_duration":2,"content":{"text":"看人吧，不一定","parse_mode":null}},{"message_id":"m027","after_start":566,"actor_id":"zimo","reply_to":null,"typing_duration":2,"content":{"text":"身边很少聊这个","parse_mode":null}},{"message_id":"m028","after_start":620,"actor_id":"linhao","reply_to":null,"typing_duration":2,"content":{"text":"确实太私密了","parse_mode":null}},{"message_id":"m029","after_start":627,"actor_id":"achen","reply_to":null,"typing_duration":1,"content":{"text":"嗯别乱传就行","parse_mode":null}},{"message_id":"m030","after_start":634,"actor_id":"zimo","reply_to":"m029","typing_duration":2,"content":{"text":"尊重别人隐私","parse_mode":null}},{"message_id":"m031","after_start":688,"actor_id":"linhao","reply_to":null,"typing_duration":1,"content":{"text":"有道理","parse_mode":null}},{"message_id":"m032","after_start":695,"actor_id":"achen","reply_to":null,"typing_duration":2,"content":{"text":"感情别弄复杂","parse_mode":null}},{"message_id":"m033","after_start":702,"actor_id":"zimo","reply_to":null,"typing_duration":2,"content":{"text":"这个最难哈哈","parse_mode":null}}]}

    script ={"version":"1","script":{"script_id":"puberty_chat_8","title":"第一次发现自己长阴毛的时候","start_at":"2026-01-01T00:00:00+08:00"},"chat":{"chat_id":0,"message_thread_id":null},"participants":[{"actor_id":"lin","name":"阿林","sender_type":"user","sender_id":1001},{"actor_id":"hao","name":"浩子","sender_type":"user","sender_id":1002},{"actor_id":"yu","name":"小宇","sender_type":"user","sender_id":1003},{"actor_id":"chen","name":"陈哥","sender_type":"user","sender_id":1004},{"actor_id":"kai","name":"凯子","sender_type":"user","sender_id":1005},{"actor_id":"mo","name":"阿墨","sender_type":"user","sender_id":1006},{"actor_id":"dong","name":"冬瓜","sender_type":"user","sender_id":1007},{"actor_id":"fei","name":"老飞","sender_type":"user","sender_id":1008}],"messages":[{"message_id":"m001","after_start":3,"actor_id":"lin","reply_to":null,"typing_duration":2,"content":{"text":"突然想起个事","parse_mode":null}},{"message_id":"m002","after_start":9,"actor_id":"lin","reply_to":null,"typing_duration":2,"content":{"text":"你们青春期尴尬吗","parse_mode":null}},{"message_id":"m003","after_start":17,"actor_id":"hao","reply_to":"m002","typing_duration":2,"content":{"text":"哪方面啊","parse_mode":null}},{"message_id":"m004","after_start":25,"actor_id":"yu","reply_to":null,"typing_duration":2,"content":{"text":"这范围可大了","parse_mode":null}},{"message_id":"m005","after_start":34,"actor_id":"lin","reply_to":null,"typing_duration":3,"content":{"text":"第一次长阴毛","parse_mode":null}},{"message_id":"m006","after_start":42,"actor_id":"chen","reply_to":"m005","typing_duration":1,"content":{"text":"草","parse_mode":null}},{"message_id":"m007","after_start":49,"actor_id":"chen","reply_to":null,"typing_duration":2,"content":{"text":"这么突然","parse_mode":null}},{"message_id":"m008","after_start":58,"actor_id":"kai","reply_to":null,"typing_duration":3,"content":{"text":"我真有印象","parse_mode":null}},{"message_id":"m009","after_start":67,"actor_id":"mo","reply_to":null,"typing_duration":2,"content":{"text":"我也记得","parse_mode":null}},{"message_id":"m010","after_start":75,"actor_id":"dong","reply_to":null,"typing_duration":2,"content":{"text":"这都能记住啊","parse_mode":null}},{"message_id":"m011","after_start":84,"actor_id":"fei","reply_to":"m010","typing_duration":2,"content":{"text":"有的人记性怪","parse_mode":null}},{"message_id":"m012","after_start":96,"actor_id":"hao","reply_to":null,"typing_duration":3,"content":{"text":"我当时还挺懵","parse_mode":null}},{"message_id":"m013","after_start":108,"actor_id":"yu","reply_to":"m012","typing_duration":2,"content":{"text":"以为出啥事了？","parse_mode":null}},{"message_id":"m014","after_start":119,"actor_id":"hao","reply_to":"m013","typing_duration":2,"content":{"text":"差不多哈哈","parse_mode":null}},{"message_id":"m015","after_start":131,"actor_id":"lin","reply_to":null,"typing_duration":3,"content":{"text":"我第一反应也是","parse_mode":null}},{"message_id":"m016","after_start":143,"actor_id":"chen","reply_to":null,"typing_duration":2,"content":{"text":"我完全没慌","parse_mode":null}},{"message_id":"m017","after_start":151,"actor_id":"chen","reply_to":null,"typing_duration":2,"content":{"text":"甚至有点新奇","parse_mode":null}},{"message_id":"m018","after_start":163,"actor_id":"kai","reply_to":"m017","typing_duration":2,"content":{"text":"观察型选手","parse_mode":null}},{"message_id":"m019","after_start":176,"actor_id":"mo","reply_to":null,"typing_duration":3,"content":{"text":"我那会最怕被发现","parse_mode":null}},{"message_id":"m020","after_start":187,"actor_id":"dong","reply_to":"m019","typing_duration":2,"content":{"text":"谁会检查你啊","parse_mode":null}},{"message_id":"m021","after_start":198,"actor_id":"mo","reply_to":null,"typing_duration":2,"content":{"text":"不知道啊","parse_mode":null}},{"message_id":"m022","after_start":205,"actor_id":"mo","reply_to":null,"typing_duration":2,"content":{"text":"当时脑子就这样","parse_mode":null}},{"message_id":"m023","after_start":219,"actor_id":"fei","reply_to":null,"typing_duration":3,"content":{"text":"青春期脑回路正常","parse_mode":null}},{"message_id":"m024","after_start":233,"actor_id":"yu","reply_to":null,"typing_duration":2,"content":{"text":"我倒是很淡定","parse_mode":null}},{"message_id":"m025","after_start":245,"actor_id":"hao","reply_to":"m024","typing_duration":2,"content":{"text":"真的假的","parse_mode":null}},{"message_id":"m026","after_start":257,"actor_id":"yu","reply_to":null,"typing_duration":3,"content":{"text":"课上讲过青春期","parse_mode":null}},{"message_id":"m027","after_start":269,"actor_id":"lin","reply_to":null,"typing_duration":2,"content":{"text":"你们课这么靠谱","parse_mode":null}},{"message_id":"m028","after_start":282,"actor_id":"kai","reply_to":null,"typing_duration":3,"content":{"text":"我们老师直接略过","parse_mode":null}},{"message_id":"m029","after_start":294,"actor_id":"dong","reply_to":"m028","typing_duration":2,"content":{"text":"经典略过","parse_mode":null}},{"message_id":"m030","after_start":306,"actor_id":"fei","reply_to":null,"typing_duration":3,"content":{"text":"一句自行阅读","parse_mode":null}},{"message_id":"m031","after_start":313,"actor_id":"fei","reply_to":null,"typing_duration":1,"content":{"text":"然后翻页","parse_mode":null}},{"message_id":"m032","after_start":328,"actor_id":"chen","reply_to":null,"typing_duration":3,"content":{"text":"老师比学生还尴尬","parse_mode":null}},{"message_id":"m033","after_start":342,"actor_id":"mo","reply_to":"m032","typing_duration":2,"content":{"text":"全班突然安静","parse_mode":null}},{"message_id":"m034","after_start":356,"actor_id":"hao","reply_to":null,"typing_duration":3,"content":{"text":"越安静越想笑","parse_mode":null}},{"message_id":"m035","after_start":368,"actor_id":"kai","reply_to":"m034","typing_duration":2,"content":{"text":"对对对","parse_mode":null}},{"message_id":"m036","after_start":380,"actor_id":"lin","reply_to":null,"typing_duration":3,"content":{"text":"我当时没人能问","parse_mode":null}},{"message_id":"m037","after_start":391,"actor_id":"yu","reply_to":"m036","typing_duration":2,"content":{"text":"你没上网搜？","parse_mode":null}},{"message_id":"m038","after_start":404,"actor_id":"lin","reply_to":null,"typing_duration":2,"content":{"text":"那会哪敢搜","parse_mode":null}},{"message_id":"m039","after_start":417,"actor_id":"dong","reply_to":null,"typing_duration":3,"content":{"text":"搜索记录像罪证","parse_mode":null}},{"message_id":"m040","after_start":429,"actor_id":"fei","reply_to":"m039","typing_duration":2,"content":{"text":"太真实了","parse_mode":null}},{"message_id":"m041","after_start":442,"actor_id":"mo","reply_to":null,"typing_duration":3,"content":{"text":"还会立刻清记录","parse_mode":null}},{"message_id":"m042","after_start":455,"actor_id":"chen","reply_to":"m041","typing_duration":2,"content":{"text":"清完才安心","parse_mode":null}},{"message_id":"m043","after_start":469,"actor_id":"hao","reply_to":null,"typing_duration":3,"content":{"text":"其实就是正常发育","parse_mode":null}},{"message_id":"m044","after_start":482,"actor_id":"yu","reply_to":"m043","typing_duration":2,"content":{"text":"现在当然知道","parse_mode":null}},{"message_id":"m045","after_start":495,"actor_id":"kai","reply_to":null,"typing_duration":3,"content":{"text":"当年可不这么想","parse_mode":null}},{"message_id":"m046","after_start":508,"actor_id":"dong","reply_to":null,"typing_duration":2,"content":{"text":"当年啥都吓人","parse_mode":null}},{"message_id":"m047","after_start":522,"actor_id":"lin","reply_to":null,"typing_duration":3,"content":{"text":"声音变了也吓人","parse_mode":null}},{"message_id":"m048","after_start":535,"actor_id":"fei","reply_to":"m047","typing_duration":2,"content":{"text":"突然破音更吓人","parse_mode":null}},{"message_id":"m049","after_start":548,"actor_id":"chen","reply_to":null,"typing_duration":2,"content":{"text":"破音是真的社死","parse_mode":null}},{"message_id":"m050","after_start":561,"actor_id":"mo","reply_to":null,"typing_duration":3,"content":{"text":"尤其回答问题时","parse_mode":null}},{"message_id":"m051","after_start":574,"actor_id":"hao","reply_to":"m050","typing_duration":2,"content":{"text":"全班憋笑那种","parse_mode":null}},{"message_id":"m052","after_start":587,"actor_id":"yu","reply_to":null,"typing_duration":3,"content":{"text":"青春期全是随机事件","parse_mode":null}},{"message_id":"m053","after_start":600,"actor_id":"kai","reply_to":"m052","typing_duration":2,"content":{"text":"身体自动更新","parse_mode":null}},{"message_id":"m054","after_start":608,"actor_id":"kai","reply_to":null,"typing_duration":1,"content":{"text":"还不给说明书","parse_mode":null}},{"message_id":"m055","after_start":622,"actor_id":"dong","reply_to":"m054","typing_duration":2,"content":{"text":"更新日志都没有","parse_mode":null}},{"message_id":"m056","after_start":635,"actor_id":"lin","reply_to":null,"typing_duration":2,"content":{"text":"笑死这个形容","parse_mode":null}},{"message_id":"m057","after_start":648,"actor_id":"fei","reply_to":null,"typing_duration":3,"content":{"text":"家长也很少细讲","parse_mode":null}},{"message_id":"m058","after_start":661,"actor_id":"chen","reply_to":"m057","typing_duration":2,"content":{"text":"我家完全不聊","parse_mode":null}},{"message_id":"m059","after_start":674,"actor_id":"mo","reply_to":null,"typing_duration":3,"content":{"text":"我家也是回避型","parse_mode":null}},{"message_id":"m060","after_start":687,"actor_id":"hao","reply_to":null,"typing_duration":2,"content":{"text":"所以全靠自己懂","parse_mode":null}},{"message_id":"m061","after_start":700,"actor_id":"yu","reply_to":"m060","typing_duration":3,"content":{"text":"还有同学瞎科普","parse_mode":null}},{"message_id":"m062","after_start":713,"actor_id":"dong","reply_to":null,"typing_duration":2,"content":{"text":"这个最危险哈哈","parse_mode":null}},{"message_id":"m063","after_start":726,"actor_id":"kai","reply_to":null,"typing_duration":3,"content":{"text":"一个比一个能编","parse_mode":null}},{"message_id":"m064","after_start":739,"actor_id":"fei","reply_to":"m063","typing_duration":2,"content":{"text":"还说得特别肯定","parse_mode":null}},{"message_id":"m065","after_start":752,"actor_id":"lin","reply_to":null,"typing_duration":3,"content":{"text":"我以前真信过","parse_mode":null}},{"message_id":"m066","after_start":765,"actor_id":"hao","reply_to":"m065","typing_duration":2,"content":{"text":"谁没信过几次","parse_mode":null}},{"message_id":"m067","after_start":778,"actor_id":"chen","reply_to":null,"typing_duration":3,"content":{"text":"现在想想挺好笑","parse_mode":null}},{"message_id":"m068","after_start":791,"actor_id":"mo","reply_to":"m067","typing_duration":2,"content":{"text":"当时可认真了","parse_mode":null}},{"message_id":"m069","after_start":804,"actor_id":"yu","reply_to":null,"typing_duration":3,"content":{"text":"主要没人解释嘛","parse_mode":null}},{"message_id":"m070","after_start":817,"actor_id":"kai","reply_to":null,"typing_duration":2,"content":{"text":"知识全靠拼图","parse_mode":null}},{"message_id":"m071","after_start":830,"actor_id":"dong","reply_to":"m070","typing_duration":2,"content":{"text":"还是缺块的拼图","parse_mode":null}},{"message_id":"m072","after_start":843,"actor_id":"fei","reply_to":null,"typing_duration":3,"content":{"text":"互联网后来救场了","parse_mode":null}},{"message_id":"m073","after_start":856,"actor_id":"hao","reply_to":"m072","typing_duration":2,"content":{"text":"前提是搜对地方","parse_mode":null}},{"message_id":"m074","after_start":869,"actor_id":"lin","reply_to":null,"typing_duration":3,"content":{"text":"别搜进奇怪论坛","parse_mode":null}},{"message_id":"m075","after_start":882,"actor_id":"chen","reply_to":"m074","typing_duration":2,"content":{"text":"越看越迷糊","parse_mode":null}},{"message_id":"m076","after_start":895,"actor_id":"mo","reply_to":null,"typing_duration":2,"content":{"text":"还容易自己吓自己","parse_mode":null}},{"message_id":"m077","after_start":908,"actor_id":"yu","reply_to":null,"typing_duration":3,"content":{"text":"正规科普最省事","parse_mode":null}},{"message_id":"m078","after_start":921,"actor_id":"kai","reply_to":"m077","typing_duration":2,"content":{"text":"现在看确实","parse_mode":null}},{"message_id":"m079","after_start":934,"actor_id":"dong","reply_to":null,"typing_duration":3,"content":{"text":"以前哪懂正规不正规","parse_mode":null}},{"message_id":"m080","after_start":947,"actor_id":"fei","reply_to":"m079","typing_duration":2,"content":{"text":"标题越吓人越点","parse_mode":null}},{"message_id":"m081","after_start":960,"actor_id":"lin","reply_to":null,"typing_duration":3,"content":{"text":"然后彻夜担心","parse_mode":null}},{"message_id":"m082","after_start":973,"actor_id":"hao","reply_to":"m081","typing_duration":2,"content":{"text":"经典症状全对上","parse_mode":null}},{"message_id":"m083","after_start":986,"actor_id":"chen","reply_to":null,"typing_duration":3,"content":{"text":"搜啥都像绝症","parse_mode":null}},{"message_id":"m084","after_start":999,"actor_id":"mo","reply_to":null,"typing_duration":2,"content":{"text":"跑题到医学了","parse_mode":null}},{"message_id":"m085","after_start":1012,"actor_id":"yu","reply_to":"m084","typing_duration":2,"content":{"text":"群聊传统艺能","parse_mode":null}},{"message_id":"m086","after_start":1025,"actor_id":"kai","reply_to":null,"typing_duration":3,"content":{"text":"原题是长阴毛吧","parse_mode":null}},{"message_id":"m087","after_start":1038,"actor_id":"dong","reply_to":"m086","typing_duration":2,"content":{"text":"终于有人拉回来","parse_mode":null}},{"message_id":"m088","after_start":1051,"actor_id":"fei","reply_to":null,"typing_duration":3,"content":{"text":"总结就是都挺懵","parse_mode":null}},{"message_id":"m089","after_start":1064,"actor_id":"lin","reply_to":"m088","typing_duration":2,"content":{"text":"而且不好意思问","parse_mode":null}},{"message_id":"m090","after_start":1077,"actor_id":"hao","reply_to":null,"typing_duration":3,"content":{"text":"其实早点科普就好","parse_mode":null}},{"message_id":"m091","after_start":1090,"actor_id":"chen","reply_to":"m090","typing_duration":2,"content":{"text":"少很多莫名焦虑","parse_mode":null}},{"message_id":"m092","after_start":1103,"actor_id":"mo","reply_to":null,"typing_duration":3,"content":{"text":"也不会觉得奇怪","parse_mode":null}},{"message_id":"m093","after_start":1116,"actor_id":"yu","reply_to":null,"typing_duration":2,"content":{"text":"本来就正常变化","parse_mode":null}},{"message_id":"m094","after_start":1129,"actor_id":"kai","reply_to":null,"typing_duration":2,"content":{"text":"身体升级罢了","parse_mode":null}},{"message_id":"m095","after_start":1142,"actor_id":"dong","reply_to":"m094","typing_duration":2,"content":{"text":"又开始更新梗了","parse_mode":null}},{"message_id":"m096","after_start":1155,"actor_id":"fei","reply_to":null,"typing_duration":2,"content":{"text":"版本青春期1.0","parse_mode":null}},{"message_id":"m097","after_start":1168,"actor_id":"lin","reply_to":"m096","typing_duration":1,"content":{"text":"bug巨多","parse_mode":null}},{"message_id":"m098","after_start":1181,"actor_id":"hao","reply_to":null,"typing_duration":2,"content":{"text":"情绪系统也乱跳","parse_mode":null}},{"message_id":"m099","after_start":1194,"actor_id":"chen","reply_to":null,"typing_duration":2,"content":{"text":"这个最难绷","parse_mode":null}},{"message_id":"m100","after_start":1207,"actor_id":"mo","reply_to":null,"typing_duration":3,"content":{"text":"突然就烦得不行","parse_mode":null}},{"message_id":"m101","after_start":1220,"actor_id":"yu","reply_to":null,"typing_duration":3,"content":{"text":"过几年再看像喜剧","parse_mode":null}},{"message_id":"m102","after_start":1233,"actor_id":"kai","reply_to":"m101","typing_duration":2,"content":{"text":"当事人当时很严肃","parse_mode":null}},{"message_id":"m103","after_start":1246,"actor_id":"dong","reply_to":null,"typing_duration":2,"content":{"text":"严肃得要命哈哈","parse_mode":null}},{"message_id":"m104","after_start":1259,"actor_id":"fei","reply_to":null,"typing_duration":3,"content":{"text":"成长就是大型误会","parse_mode":null}},{"message_id":"m105","after_start":1272,"actor_id":"lin","reply_to":"m104","typing_duration":2,"content":{"text":"这句可以结题","parse_mode":null}},{"message_id":"m106","after_start":1285,"actor_id":"hao","reply_to":null,"typing_duration":2,"content":{"text":"批准结题","parse_mode":null}},{"message_id":"m107","after_start":1298,"actor_id":"chen","reply_to":null,"typing_duration":2,"content":{"text":"下次聊点正常的","parse_mode":null}},{"message_id":"m108","after_start":1311,"actor_id":"mo","reply_to":"m107","typing_duration":1,"content":{"text":"你先定义正常","parse_mode":null}},{"message_id":"m109","after_start":1324,"actor_id":"yu","reply_to":null,"typing_duration":2,"content":{"text":"这群没有正常话题","parse_mode":null}},{"message_id":"m110","after_start":1337,"actor_id":"kai","reply_to":"m109","typing_duration":2,"content":{"text":"确实","parse_mode":null}},{"message_id":"m111","after_start":1350,"actor_id":"dong","reply_to":null,"typing_duration":2,"content":{"text":"散会散会","parse_mode":null}},{"message_id":"m112","after_start":1363,"actor_id":"fei","reply_to":"m111","typing_duration":2,"content":{"text":"五分钟后继续跑题","parse_mode":null}}]}
    script["version"] = "1.0"
    script.pop("chat", None)
    script["script"]["start_at"] = (
        datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(seconds=10)
    ).isoformat()

    session_set={}
    #Mathis
    session_set[0] = "1AZWarzwBu1w3WOHI3EDinm3r-9WaUwkgZdSciQu5IQ68VlSHdCinfnY29Z2fwOcJdv-pnqwDfiiRX-q9xyYvNHQ_kM8zRLdrHeRf3vokmUvqCMuaQu_DqguAhE-i4G0BNfeLSJLyb_M8QdMu663tuF_sutdztJ3V4yBKKHpblNxNzaIYX4Slljuc0bpjlMMYhCUf3bGXiEw7boHm-lW5gVvCg14oQUmoDYmRyuT6GEc5XivvYt4Lel9VPz7z84s3qp1ZDzsAq9OOHclufoU2RbkOE5ZtUdbws-cjqbd6MeOhwmVy-JmdgnktcIT4TiB4JY9g6BDoQb3JTayqjpf7A7AAmrr8HwI="

    #https://t.me/smith238134
    session_set[1] = "1AZWarzwBu2J2UQ80TXTVK4wxI48_toH794Jjo9PKYKYcfMfKSxfAK1k232o4Vtsm2FY-cdI68aW07YcNdGxyuj1XBB8ICVF1kg7vqhgjH2PsLlF3A6NmfS1fgzh3G3Pg8Sp-1ES-e0qn8G-Z3S8RkkRIPTzcdphUnrr54fOps9qqNUuWvIxaZLIzuggftjctVG5B3BsnYZ9VCD4RtnSt-mXimq3B8TECTJjEtfe-6N2qwLAzi9IYsUdfgQ9r_VjFkMAM4Q_W5EaPA2QKja0fpj1F3EkhM1M4S0f3xHCObwnI5h2e8paJiSoQ-Qvk3uCdzp0_ShlSI9RMlzsZKXLwvGCU68z6ob4="

    #https://t.me/allan04823223
    session_set[2] = "1AZWarzwBu62evXgabN1UcaLS6U-BzlyMvuudHnOv0PTTREZRTebs6QVb3qbrC1gI-MGLc41ySY2DJqvgpj3wFQ-aGpP1ckahf0lyVlsXx6pgpZMFw5HKQ0PUjHteiJe8O39TDrvWwXJO-47IrWSI-tiaU4BZImq7-SxR3IFbRnwqxhUvGjmWWLMlD0pUJFQM8KJGBVVS9INvRh7NzV1xliTrsp6JLfushhB3XJQQ45_dm1c3CLsDrhJIT27ejmC7Uro9XyQh8EiveRSTaJDZvctRQRmNvCeKlTf6anGqN4cFLfhvg98R8Fo1Y-hS4yuvfMBlHHpaaLnvoO9ayAUVoEu9-8Dvbx8="

    #https://t.me/egg47223
    session_set[3] = "1AZWarzwBu5FSUp6B7qadq0JoWosPjs2dcx1EtY3kqWMXIoSzkwsoC2LIMqFD42AjthfBCSFzJ1sFlqN8d5bMHXpqKzqVwt1s7EWEJ8TTbEfbtlCC4HDuODsB2rYb_3HhdOs7WQA59GbJyUK_LbVeL2kKNNFGIDsSB77D019tVvEk949NIbM6Bod-iST0fu1zMb4olE3emuxMZgNkzJc0R_Szv0HjQ2E080zMND1uNSOITHgRHuGBkZmPAZaYDRuNjvhSHIVwlzRmCgz6HoLFbEBd1S9gerGCM3g_mrxXS9yeKQ6ygAR4cKye0j9OnlO-noUB-BbzGGfGK4_4H_1Whs7QF6TeHb0="

    #十八
    session_set[4] = "1AZWarzwBu7TJWcxVufZpeo6YadubO3GNEsEaQdIPvqpOxnP3F4N4oO0hJ1kNj1_gPYZtMQ7XYUnGu-lhWEYzB33J0CNJyxvClFWfP41M6n3EUSS-zb_4L1_WCmTx362Y3uBavlmcqHiz9ipO3oonQyzhkwRqJpLx-zDhL5VTAA_bNeHzSQhc_xR2yCinJ9WIUxBtm5UmSimglQiL4ULpFJ3dlenPKQpe-MSesfDX9iARDbrrmSGIfeFVt0XhwodfD-Bxu4yn3Xm7XOXSxmuI6K9X1lgIhMBNBVrw2BYe49r4IJUOOoJd4mV6Hre0fUe6x2CYxPnKjjXX4hBI6fws6_A9nqbGumU="

    #Hello
    session_set[5] = "1AZWarzwBu4Eo7yprGWduZowwJK9vvd4ZvQ_BpiDtjFzzSARgK0X2Ac8LjKlKk5puxzMNi4I-gOJKTL7NM03wPrV2p3n0KozyV9tDNtbazkeEQSTpMFJ4WlGISO-U8SIBmdi3-oRwSlrNotAdsZq90vZDJXkyMjP_TKR3l079KG3x1QYySyOAHpxdSIi0xhK4EhWUKjU56HSod0jFR0WS4gZPB5kkIFCdYkjUmvcROuzbFZ6ifFExoqGF9SVGSeeA7nPU5Ruo-xiH2xt-Zg9UhLFVToC2-NGICLZe8mj4ynqCVmEPbeQ2HLB6D0_A6qYUMbUbKhH8HhiJ13FkJahGZazA0RaB8o8="

    #Jbujphcr
    session_set[6] = "1AZWarzwBu49w-0TDtzH44lzjM_2ycNo2nHAMvtfYBi7cvz54zDmVLtMWDP3x9EgwgOwdn9reuqtnRZE1DDpzl-aFvNmKDvPn8l8d8LC4gNakUEjOtNpVP3DvSYLKBOqyyZPNus7Fwxm5tXnqRPEY0hpYj1OEgD29LEtzrczVvNAcfzlHgmK4f5mtD0l3tHLXNEbFPtgjc7wO0nvY6BgZuIDqvL22FzyHT3rvTp-nApTC3mFoOTFbzMK6NOeHkjJYFX5y2t9_MzdRlxaCBGLMHG42fbvEGCZNU4b8oB9YswGyVXI2NpGXIWlIggwfoMn9AF9zJRRJTSCPoh2-M5ALOMAH1pmIDcQ="

    #PXM
    session_set[7] = "1BVtsOGcBu4pM7veqeWVCl8hblhIp9aczOpz0McRxcBT8hTr3GvQ24Jm8Vx-cHx63yoBna1iJ74ZCikAS4cC--nMN4FliAGHn5MDP_FLJkD_jxS4oJAW09U8kQuP0DMEF3wAtuRWzkMbgSQUtRUyDuL1jz1VkSNcvLcbILNweq-W5C-qDLSGyEia_WGxs17agmk9btuJgz0OnXPQu2TgMiAJgZbNxN9gebIPZUwNpMEqxkgfmtmvrT0MG4AOMVL8dtVRPq_jCiMYGqhND1KvTAjWnZFWbR38xxGYTfULPQNN49vbZM3sOnoktseyWooUZpWrLD8Vp2aCLaLKek2I95VuY2KWVgNs="


    account_configs = {}
    participant_count = len(script["participants"])
    if len(session_set) < participant_count:
        raise RuntimeError(
            f"StringSession 数量不足：需要 {participant_count} 个，只有 {len(session_set)} 个"
        )

    for participant, session_string in zip(
        script["participants"],
        session_set.values(),
    ):
        account_configs[str(participant["sender_id"])] = {
            "api_id": int(os.environ["API_ID"]),
            "api_hash": os.environ["API_HASH"],
            "session_string": session_string,
        }
    chat_id = -1004335920222
    chat_invite_link = os.getenv("CHAT_INVITE_LINK", "").strip() or None

   
    # chat_id: int | str = os.environ["CHAT_ID"].strip()
    # if chat_id.lstrip("-").isdigit():
    #     chat_id = int(chat_id)

    try:
        result = await HumanBotOperator.run_chat_script(
            script_json=script,
            chat_id=chat_id,
            message_thread_id=None,
            account_configs=account_configs,
            chat_invite_link=chat_invite_link,
            fast_mode=False,
        )
        print(f"聊天脚本执行结果：{result}", flush=True)
    finally:
        await MySQLPool.close()


async def run_telethon_bot(
    config: dict | None = None,
    *,
    configure_mysql: bool = True,
) -> None:
    print("正在启动 Telethon 用户账号流程...", flush=True)
    if config is None:
        account_manager = UserAccountManager()
        config = account_manager.load_config()
    if configure_mysql:
        configure_mysql_pool(config)
    try:
        session_set = {}

        #Mathis
        session_set[0] = "1AZWarzwBu1w3WOHI3EDinm3r-9WaUwkgZdSciQu5IQ68VlSHdCinfnY29Z2fwOcJdv-pnqwDfiiRX-q9xyYvNHQ_kM8zRLdrHeRf3vokmUvqCMuaQu_DqguAhE-i4G0BNfeLSJLyb_M8QdMu663tuF_sutdztJ3V4yBKKHpblNxNzaIYX4Slljuc0bpjlMMYhCUf3bGXiEw7boHm-lW5gVvCg14oQUmoDYmRyuT6GEc5XivvYt4Lel9VPz7z84s3qp1ZDzsAq9OOHclufoU2RbkOE5ZtUdbws-cjqbd6MeOhwmVy-JmdgnktcIT4TiB4JY9g6BDoQb3JTayqjpf7A7AAmrr8HwI="

        #https://t.me/smith238134
        session_set[1] = "1AZWarzwBu2J2UQ80TXTVK4wxI48_toH794Jjo9PKYKYcfMfKSxfAK1k232o4Vtsm2FY-cdI68aW07YcNdGxyuj1XBB8ICVF1kg7vqhgjH2PsLlF3A6NmfS1fgzh3G3Pg8Sp-1ES-e0qn8G-Z3S8RkkRIPTzcdphUnrr54fOps9qqNUuWvIxaZLIzuggftjctVG5B3BsnYZ9VCD4RtnSt-mXimq3B8TECTJjEtfe-6N2qwLAzi9IYsUdfgQ9r_VjFkMAM4Q_W5EaPA2QKja0fpj1F3EkhM1M4S0f3xHCObwnI5h2e8paJiSoQ-Qvk3uCdzp0_ShlSI9RMlzsZKXLwvGCU68z6ob4="

        #https://t.me/allan04823223
        session_set[2] = "1AZWarzwBu62evXgabN1UcaLS6U-BzlyMvuudHnOv0PTTREZRTebs6QVb3qbrC1gI-MGLc41ySY2DJqvgpj3wFQ-aGpP1ckahf0lyVlsXx6pgpZMFw5HKQ0PUjHteiJe8O39TDrvWwXJO-47IrWSI-tiaU4BZImq7-SxR3IFbRnwqxhUvGjmWWLMlD0pUJFQM8KJGBVVS9INvRh7NzV1xliTrsp6JLfushhB3XJQQ45_dm1c3CLsDrhJIT27ejmC7Uro9XyQh8EiveRSTaJDZvctRQRmNvCeKlTf6anGqN4cFLfhvg98R8Fo1Y-hS4yuvfMBlHHpaaLnvoO9ayAUVoEu9-8Dvbx8="

        #https://t.me/egg47223
        session_set[3] = "1AZWarzwBu5FSUp6B7qadq0JoWosPjs2dcx1EtY3kqWMXIoSzkwsoC2LIMqFD42AjthfBCSFzJ1sFlqN8d5bMHXpqKzqVwt1s7EWEJ8TTbEfbtlCC4HDuODsB2rYb_3HhdOs7WQA59GbJyUK_LbVeL2kKNNFGIDsSB77D019tVvEk949NIbM6Bod-iST0fu1zMb4olE3emuxMZgNkzJc0R_Szv0HjQ2E080zMND1uNSOITHgRHuGBkZmPAZaYDRuNjvhSHIVwlzRmCgz6HoLFbEBd1S9gerGCM3g_mrxXS9yeKQ6ygAR4cKye0j9OnlO-noUB-BbzGGfGK4_4H_1Whs7QF6TeHb0="

        #十八
        session_set[4] = "1AZWarzwBu7TJWcxVufZpeo6YadubO3GNEsEaQdIPvqpOxnP3F4N4oO0hJ1kNj1_gPYZtMQ7XYUnGu-lhWEYzB33J0CNJyxvClFWfP41M6n3EUSS-zb_4L1_WCmTx362Y3uBavlmcqHiz9ipO3oonQyzhkwRqJpLx-zDhL5VTAA_bNeHzSQhc_xR2yCinJ9WIUxBtm5UmSimglQiL4ULpFJ3dlenPKQpe-MSesfDX9iARDbrrmSGIfeFVt0XhwodfD-Bxu4yn3Xm7XOXSxmuI6K9X1lgIhMBNBVrw2BYe49r4IJUOOoJd4mV6Hre0fUe6x2CYxPnKjjXX4hBI6fws6_A9nqbGumU="

        #Hello
        session_set[5] = "1AZWarzwBu4Eo7yprGWduZowwJK9vvd4ZvQ_BpiDtjFzzSARgK0X2Ac8LjKlKk5puxzMNi4I-gOJKTL7NM03wPrV2p3n0KozyV9tDNtbazkeEQSTpMFJ4WlGISO-U8SIBmdi3-oRwSlrNotAdsZq90vZDJXkyMjP_TKR3l079KG3x1QYySyOAHpxdSIi0xhK4EhWUKjU56HSod0jFR0WS4gZPB5kkIFCdYkjUmvcROuzbFZ6ifFExoqGF9SVGSeeA7nPU5Ruo-xiH2xt-Zg9UhLFVToC2-NGICLZe8mj4ynqCVmEPbeQ2HLB6D0_A6qYUMbUbKhH8HhiJ13FkJahGZazA0RaB8o8="

        #Jbujphcr
        session_set[6] = "1AZWarzwBu49w-0TDtzH44lzjM_2ycNo2nHAMvtfYBi7cvz54zDmVLtMWDP3x9EgwgOwdn9reuqtnRZE1DDpzl-aFvNmKDvPn8l8d8LC4gNakUEjOtNpVP3DvSYLKBOqyyZPNus7Fwxm5tXnqRPEY0hpYj1OEgD29LEtzrczVvNAcfzlHgmK4f5mtD0l3tHLXNEbFPtgjc7wO0nvY6BgZuIDqvL22FzyHT3rvTp-nApTC3mFoOTFbzMK6NOeHkjJYFX5y2t9_MzdRlxaCBGLMHG42fbvEGCZNU4b8oB9YswGyVXI2NpGXIWlIggwfoMn9AF9zJRRJTSCPoh2-M5ALOMAH1pmIDcQ="
        

        #PXM
        session_set[7] = "1BVtsOGcBu4pM7veqeWVCl8hblhIp9aczOpz0McRxcBT8hTr3GvQ24Jm8Vx-cHx63yoBna1iJ74ZCikAS4cC--nMN4FliAGHn5MDP_FLJkD_jxS4oJAW09U8kQuP0DMEF3wAtuRWzkMbgSQUtRUyDuL1jz1VkSNcvLcbILNweq-W5C-qDLSGyEia_WGxs17agmk9btuJgz0OnXPQu2TgMiAJgZbNxN9gebIPZUwNpMEqxkgfmtmvrT0MG4AOMVL8dtVRPq_jCiMYGqhND1KvTAjWnZFWbR38xxGYTfULPQNN49vbZM3sOnoktseyWooUZpWrLD8Vp2aCLaLKek2I95VuY2KWVgNs="

        operator = {}

        # 随机从 session_set 中选择，形成另外的子集合
        selected_sessions = random.sample(list(session_set.values()), 8)

        # selected_sessions[0] = session_set[7]

        # 遍循 selected_sessions
        
        for i, session in enumerate(selected_sessions):
            try:
                operator_length = len(operator)

                operator[(operator_length)] = await HumanBotOperator.login_with_session(session_string=session, api_id=API_ID, api_hash=API_HASH)
                #将 operator_opp 添加到 operator 字典中
                # operator[i] = operator_opp
            except Exception as e:
                print(f"Failed to login with session {i} {session}: {e}", flush=True)

            
            # await operator.join_chat("https://t.me/+i5S7P-Dol4dhNzA5")  #加入布吉岛主 1004335920222
            # await operator.join_chat("https://t.me/+iHyXV6FFCQAxN2Ix")  #加入布吉岛
            # https://t.me/+LmR0F1WpnFQ0Y2Ix
        
        for i, session in enumerate(operator):
            op = operator[i] 

            await op.update_profile(first_name="Mathis ",last_name="")

            # await op.join_chat("https://t.me/+LmR0F1WpnFQ0Y2Ix")  #测试群
        
            
            # await op.send_random_message(chat_id=[-1004335920222, -1004372020134])

            await op.tracking_message_range(chat=-1004335920222)
            await op.tracking_message_range(chat=-1004372020134)
            # while True:
            # for i in range(5):
                # r = await op.extract()
                # 随机休息 10~25 秒
                # print(f"提取结果: {r}", flush=True)

                # sleep_time = random.randint(10, 25)
                # await asyncio.sleep(sleep_time)
            # await op.send_first_video_to_bot(source_chat=7613284106,target_bot="@di5k2bot",search_limit=5000)


            # await op.join_chat("https://t.me/+HYvGBwaTSUEyYzkx")  #正太方舟
            # await op.client.send_message("@posterre_bot", "/checkin")

            # sleep_time = random.randint(5, 15)
            # await asyncio.sleep(sleep_time)
        
       
        # for i, session in enumerate(operator):
            await op.disconnect()
        # await account_manager.check_all_userbot(config)
        # await account_manager.rec_new_account(
        #     phone_number="+15809565862",
        #     pw2fa="z4422404",
        # )
        # await account_manager.check_phone("+18157706388")
    finally:
        await MySQLPool.close()


def configure_mysql_pool(config: dict) -> None:
    """使用统一配置初始化 MySQLPool。"""
    MySQLPool.configure(
        host=config.get("db_host", os.getenv("MYSQL_DB_HOST", "localhost")),
        user=config.get("db_user", os.getenv("MYSQL_DB_USER", "")),
        password=config.get("db_password", os.getenv("MYSQL_DB_PASSWORD", "")),
        database=config.get("db_name", os.getenv("MYSQL_DB_NAME", "")),
        port=int(config.get("db_port", os.getenv("MYSQL_DB_PORT", 3306))),
    )


async def main2() -> None:
    """同时执行 Telethon 用户账号流程与 Aiogram Bot polling。"""
    account_manager = UserAccountManager()
    config = account_manager.load_config()
    configure_mysql_pool(config)
    print("正在并发启动 Aiogram 与 Telethon...", flush=True)
    aiogram_operator = AiogramBotOperator(config)
    aiogram_task = asyncio.create_task(
        aiogram_operator.run(),
        name="aiogram-bot-polling",
    )
    telethon_task = asyncio.create_task(
        run_telethon_bot(config, configure_mysql=False),
        name="telethon-user-flow",
    )

    try:
        await asyncio.gather(aiogram_task, telethon_task)
    finally:
        tasks = [aiogram_task, telethon_task]
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main2())
