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

    script ={"version":"1","script":{"script_id":"lin_ziye_works_status_8p_001","title":"聊林子烨小时候的作品和近况","start_at":"2026-01-01T00:00:00+08:00"},"chat":{"chat_id":0,"message_thread_id":null},"participants":[{"actor_id":"a_chen","name":"阿辰","sender_type":"user","sender_id":1001},{"actor_id":"a_he","name":"小何","sender_type":"user","sender_id":1002},{"actor_id":"a_yu","name":"阿屿","sender_type":"user","sender_id":1003},{"actor_id":"a_ke","name":"可乐","sender_type":"user","sender_id":1004},{"actor_id":"a_mo","name":"墨鱼","sender_type":"user","sender_id":1005},{"actor_id":"a_lin","name":"林同学","sender_type":"user","sender_id":1006},{"actor_id":"a_qi","name":"七仔","sender_type":"user","sender_id":1007},{"actor_id":"a_mu","name":"木头","sender_type":"user","sender_id":1008}],"messages":[{"message_id":"m001","after_start":5,"actor_id":"a_chen","reply_to":null,"typing_duration":2,"content":{"text":"林子烨吗","parse_mode":null}},{"message_id":"m002","after_start":11,"actor_id":"a_he","reply_to":"m001","typing_duration":1,"content":{"text":"当然记得","parse_mode":null}},{"message_id":"m003","after_start":18,"actor_id":"a_yu","reply_to":null,"typing_duration":2,"content":{"text":"雪重子那个？","parse_mode":null}},{"message_id":"m004","after_start":25,"actor_id":"a_ke","reply_to":"m003","typing_duration":1,"content":{"text":"对就是他","parse_mode":null}},{"message_id":"m005","after_start":32,"actor_id":"a_mo","reply_to":null,"typing_duration":2,"content":{"text":"我先认识裴之","parse_mode":null}},{"message_id":"m006","after_start":39,"actor_id":"a_lin","reply_to":null,"typing_duration":2,"content":{"text":"天才基本法吧","parse_mode":null}},{"message_id":"m007","after_start":46,"actor_id":"a_qi","reply_to":"m006","typing_duration":1,"content":{"text":"少年裴之","parse_mode":null}},{"message_id":"m008","after_start":53,"actor_id":"a_mu","reply_to":null,"typing_duration":2,"content":{"text":"那会真的很小","parse_mode":null}},{"message_id":"m009","after_start":72,"actor_id":"a_chen","reply_to":null,"typing_duration":2,"content":{"text":"他11年出生的","parse_mode":null}},{"message_id":"m010","after_start":79,"actor_id":"a_he","reply_to":null,"typing_duration":2,"content":{"text":"出道也挺早","parse_mode":null}},{"message_id":"m011","after_start":86,"actor_id":"a_yu","reply_to":null,"typing_duration":2,"content":{"text":"君九龄也有他","parse_mode":null}},{"message_id":"m012","after_start":93,"actor_id":"a_ke","reply_to":"m011","typing_duration":2,"content":{"text":"演楚九褣吧","parse_mode":null}},{"message_id":"m013","after_start":100,"actor_id":"a_mo","reply_to":null,"typing_duration":2,"content":{"text":"完美伴侣也演了","parse_mode":null}},{"message_id":"m014","after_start":107,"actor_id":"a_lin","reply_to":null,"typing_duration":2,"content":{"text":"那部叫林靖","parse_mode":null}},{"message_id":"m015","after_start":114,"actor_id":"a_qi","reply_to":null,"typing_duration":2,"content":{"text":"小时候作品真不少","parse_mode":null}},{"message_id":"m016","after_start":121,"actor_id":"a_mu","reply_to":null,"typing_duration":2,"content":{"text":"题材还挺杂","parse_mode":null}},{"message_id":"m017","after_start":139,"actor_id":"a_chen","reply_to":null,"typing_duration":2,"content":{"text":"还有暗恋橘生淮南","parse_mode":null}},{"message_id":"m018","after_start":146,"actor_id":"a_he","reply_to":null,"typing_duration":2,"content":{"text":"少年盛淮南","parse_mode":null}},{"message_id":"m019","after_start":153,"actor_id":"a_yu","reply_to":null,"typing_duration":2,"content":{"text":"我居然漏了这个","parse_mode":null}},{"message_id":"m020","after_start":160,"actor_id":"a_ke","reply_to":"m019","typing_duration":1,"content":{"text":"戏路挺广的","parse_mode":null}},{"message_id":"m021","after_start":167,"actor_id":"a_mo","reply_to":null,"typing_duration":2,"content":{"text":"现代古装都拍","parse_mode":null}},{"message_id":"m022","after_start":174,"actor_id":"a_lin","reply_to":null,"typing_duration":2,"content":{"text":"后来古装更多","parse_mode":null}},{"message_id":"m023","after_start":181,"actor_id":"a_qi","reply_to":null,"typing_duration":2,"content":{"text":"云之羽很出圈","parse_mode":null}},{"message_id":"m024","after_start":188,"actor_id":"a_mu","reply_to":"m023","typing_duration":1,"content":{"text":"雪重子确实","parse_mode":null}},{"message_id":"m025","after_start":206,"actor_id":"a_chen","reply_to":null,"typing_duration":2,"content":{"text":"那个角色很特别","parse_mode":null}},{"message_id":"m026","after_start":213,"actor_id":"a_he","reply_to":null,"typing_duration":2,"content":{"text":"人小但气场冷","parse_mode":null}},{"message_id":"m027","after_start":220,"actor_id":"a_yu","reply_to":null,"typing_duration":2,"content":{"text":"辨识度一下有了","parse_mode":null}},{"message_id":"m028","after_start":227,"actor_id":"a_ke","reply_to":null,"typing_duration":2,"content":{"text":"一念关山也有他","parse_mode":null}},{"message_id":"m029","after_start":234,"actor_id":"a_mo","reply_to":"m028","typing_duration":1,"content":{"text":"宁十三","parse_mode":null}},{"message_id":"m030","after_start":241,"actor_id":"a_lin","reply_to":null,"typing_duration":2,"content":{"text":"那几年连着刷脸","parse_mode":null}},{"message_id":"m031","after_start":248,"actor_id":"a_qi","reply_to":null,"typing_duration":2,"content":{"text":"但角色不太重复","parse_mode":null}},{"message_id":"m032","after_start":255,"actor_id":"a_mu","reply_to":null,"typing_duration":2,"content":{"text":"这点挺难得","parse_mode":null}},{"message_id":"m033","after_start":273,"actor_id":"a_chen","reply_to":null,"typing_duration":2,"content":{"text":"大梦归离看了吗","parse_mode":null}},{"message_id":"m034","after_start":280,"actor_id":"a_he","reply_to":"m033","typing_duration":1,"content":{"text":"看了白玖","parse_mode":null}},{"message_id":"m035","after_start":287,"actor_id":"a_yu","reply_to":null,"typing_duration":2,"content":{"text":"那时候明显长大了","parse_mode":null}},{"message_id":"m036","after_start":294,"actor_id":"a_ke","reply_to":null,"typing_duration":2,"content":{"text":"跟裴之时期差好多","parse_mode":null}},{"message_id":"m037","after_start":301,"actor_id":"a_mo","reply_to":null,"typing_duration":2,"content":{"text":"童星变化就是快","parse_mode":null}},{"message_id":"m038","after_start":308,"actor_id":"a_lin","reply_to":null,"typing_duration":2,"content":{"text":"演法也更放开了","parse_mode":null}},{"message_id":"m039","after_start":315,"actor_id":"a_qi","reply_to":null,"typing_duration":2,"content":{"text":"白玖挺活泼的","parse_mode":null}},{"message_id":"m040","after_start":322,"actor_id":"a_mu","reply_to":null,"typing_duration":2,"content":{"text":"和雪重子两路人","parse_mode":null}},{"message_id":"m041","after_start":340,"actor_id":"a_chen","reply_to":null,"typing_duration":2,"content":{"text":"这两角色反差大","parse_mode":null}},{"message_id":"m042","after_start":347,"actor_id":"a_he","reply_to":null,"typing_duration":2,"content":{"text":"一个冷一个灵","parse_mode":null}},{"message_id":"m043","after_start":354,"actor_id":"a_yu","reply_to":null,"typing_duration":2,"content":{"text":"我还是偏爱裴之","parse_mode":null}},{"message_id":"m044","after_start":361,"actor_id":"a_ke","reply_to":"m043","typing_duration":2,"content":{"text":"安静型角色适合他","parse_mode":null}},{"message_id":"m045","after_start":368,"actor_id":"a_mo","reply_to":null,"typing_duration":2,"content":{"text":"我投雪重子","parse_mode":null}},{"message_id":"m046","after_start":375,"actor_id":"a_lin","reply_to":null,"typing_duration":2,"content":{"text":"古装记忆点更强","parse_mode":null}},{"message_id":"m047","after_start":382,"actor_id":"a_qi","reply_to":null,"typing_duration":2,"content":{"text":"白玖也挺讨喜","parse_mode":null}},{"message_id":"m048","after_start":389,"actor_id":"a_mu","reply_to":null,"typing_duration":2,"content":{"text":"你们开始投票了","parse_mode":null}},{"message_id":"m049","after_start":407,"actor_id":"a_chen","reply_to":null,"typing_duration":2,"content":{"text":"说回最近吧","parse_mode":null}},{"message_id":"m050","after_start":414,"actor_id":"a_he","reply_to":null,"typing_duration":2,"content":{"text":"现在还一直拍戏","parse_mode":null}},{"message_id":"m051","after_start":421,"actor_id":"a_yu","reply_to":null,"typing_duration":2,"content":{"text":"百花杀有天圆","parse_mode":null}},{"message_id":"m052","after_start":428,"actor_id":"a_ke","reply_to":null,"typing_duration":2,"content":{"text":"新项目也不少","parse_mode":null}},{"message_id":"m053","after_start":435,"actor_id":"a_mo","reply_to":null,"typing_duration":2,"content":{"text":"来战也有他","parse_mode":null}},{"message_id":"m054","after_start":442,"actor_id":"a_lin","reply_to":null,"typing_duration":2,"content":{"text":"演小狼妖","parse_mode":null}},{"message_id":"m055","after_start":449,"actor_id":"a_qi","reply_to":null,"typing_duration":2,"content":{"text":"窈窈有期也拍了","parse_mode":null}},{"message_id":"m056","after_start":456,"actor_id":"a_mu","reply_to":"m055","typing_duration":2,"content":{"text":"今年已经杀青","parse_mode":null}},{"message_id":"m057","after_start":474,"actor_id":"a_chen","reply_to":null,"typing_duration":2,"content":{"text":"还有万花世界","parse_mode":null}},{"message_id":"m058","after_start":481,"actor_id":"a_he","reply_to":null,"typing_duration":2,"content":{"text":"五月开的机吧","parse_mode":null}},{"message_id":"m059","after_start":488,"actor_id":"a_yu","reply_to":null,"typing_duration":2,"content":{"text":"行程确实挺满","parse_mode":null}},{"message_id":"m060","after_start":495,"actor_id":"a_ke","reply_to":null,"typing_duration":2,"content":{"text":"今年还有澎湖海战","parse_mode":null}},{"message_id":"m061","after_start":502,"actor_id":"a_mo","reply_to":"m060","typing_duration":2,"content":{"text":"演郑克塽那个","parse_mode":null}},{"message_id":"m062","after_start":509,"actor_id":"a_lin","reply_to":null,"typing_duration":2,"content":{"text":"电影线也没停","parse_mode":null}},{"message_id":"m063","after_start":516,"actor_id":"a_qi","reply_to":null,"typing_duration":2,"content":{"text":"十五岁履历挺长","parse_mode":null}},{"message_id":"m064","after_start":523,"actor_id":"a_mu","reply_to":null,"typing_duration":2,"content":{"text":"翻作品表会吓到","parse_mode":null}},{"message_id":"m065","after_start":541,"actor_id":"a_chen","reply_to":null,"typing_duration":2,"content":{"text":"731也值得提","parse_mode":null}},{"message_id":"m066","after_start":548,"actor_id":"a_he","reply_to":"m065","typing_duration":2,"content":{"text":"他演孙明亮","parse_mode":null}},{"message_id":"m067","after_start":555,"actor_id":"a_yu","reply_to":null,"typing_duration":2,"content":{"text":"题材一下变重了","parse_mode":null}},{"message_id":"m068","after_start":562,"actor_id":"a_ke","reply_to":null,"typing_duration":2,"content":{"text":"和古偶完全不同","parse_mode":null}},{"message_id":"m069","after_start":569,"actor_id":"a_mo","reply_to":null,"typing_duration":2,"content":{"text":"这种经历挺锻炼人","parse_mode":null}},{"message_id":"m070","after_start":576,"actor_id":"a_lin","reply_to":null,"typing_duration":2,"content":{"text":"作品跨度越来越大","parse_mode":null}},{"message_id":"m071","after_start":583,"actor_id":"a_qi","reply_to":null,"typing_duration":2,"content":{"text":"不是只拍一种类型","parse_mode":null}},{"message_id":"m072","after_start":590,"actor_id":"a_mu","reply_to":null,"typing_duration":2,"content":{"text":"对演员挺重要","parse_mode":null}},{"message_id":"m073","after_start":608,"actor_id":"a_chen","reply_to":null,"typing_duration":2,"content":{"text":"最近微博也有更新","parse_mode":null}},{"message_id":"m074","after_start":615,"actor_id":"a_he","reply_to":null,"typing_duration":2,"content":{"text":"八月还发了日常","parse_mode":null}},{"message_id":"m075","after_start":622,"actor_id":"a_yu","reply_to":null,"typing_duration":2,"content":{"text":"浮生也杀青了吧","parse_mode":null}},{"message_id":"m076","after_start":629,"actor_id":"a_ke","reply_to":"m075","typing_duration":1,"content":{"text":"八月杀青","parse_mode":null}},{"message_id":"m077","after_start":636,"actor_id":"a_mo","reply_to":null,"typing_duration":2,"content":{"text":"感觉一直在进组","parse_mode":null}},{"message_id":"m078","after_start":643,"actor_id":"a_lin","reply_to":null,"typing_duration":2,"content":{"text":"成长速度确实快","parse_mode":null}},{"message_id":"m079","after_start":650,"actor_id":"a_qi","reply_to":null,"typing_duration":2,"content":{"text":"但毕竟还在读书","parse_mode":null}},{"message_id":"m080","after_start":657,"actor_id":"a_mu","reply_to":null,"typing_duration":2,"content":{"text":"还是别催着长大","parse_mode":null}},{"message_id":"m081","after_start":675,"actor_id":"a_chen","reply_to":null,"typing_duration":2,"content":{"text":"看作品慢慢变化呗","parse_mode":null}},{"message_id":"m082","after_start":682,"actor_id":"a_he","reply_to":null,"typing_duration":2,"content":{"text":"从童星到少年演员","parse_mode":null}},{"message_id":"m083","after_start":689,"actor_id":"a_yu","reply_to":null,"typing_duration":2,"content":{"text":"这个阶段挺关键","parse_mode":null}},{"message_id":"m084","after_start":696,"actor_id":"a_ke","reply_to":null,"typing_duration":2,"content":{"text":"选角色也会变","parse_mode":null}},{"message_id":"m085","after_start":703,"actor_id":"a_mo","reply_to":null,"typing_duration":2,"content":{"text":"以后现代戏多来点","parse_mode":null}},{"message_id":"m086","after_start":710,"actor_id":"a_lin","reply_to":"m085","typing_duration":2,"content":{"text":"我也想看现代戏","parse_mode":null}},{"message_id":"m087","after_start":717,"actor_id":"a_qi","reply_to":null,"typing_duration":2,"content":{"text":"我还想看悬疑","parse_mode":null}},{"message_id":"m088","after_start":724,"actor_id":"a_mu","reply_to":null,"typing_duration":2,"content":{"text":"你们已经点菜了","parse_mode":null}},{"message_id":"m089","after_start":742,"actor_id":"a_chen","reply_to":null,"typing_duration":2,"content":{"text":"古装也别彻底丢","parse_mode":null}},{"message_id":"m090","after_start":749,"actor_id":"a_he","reply_to":null,"typing_duration":2,"content":{"text":"古装确实有优势","parse_mode":null}},{"message_id":"m091","after_start":756,"actor_id":"a_yu","reply_to":null,"typing_duration":2,"content":{"text":"雪重子滤镜太深","parse_mode":null}},{"message_id":"m092","after_start":763,"actor_id":"a_ke","reply_to":null,"typing_duration":2,"content":{"text":"裴之党不同意","parse_mode":null}},{"message_id":"m093","after_start":770,"actor_id":"a_mo","reply_to":"m092","typing_duration":1,"content":{"text":"又打起来了","parse_mode":null}},{"message_id":"m094","after_start":777,"actor_id":"a_lin","reply_to":null,"typing_duration":2,"content":{"text":"白玖党路过","parse_mode":null}},{"message_id":"m095","after_start":784,"actor_id":"a_qi","reply_to":null,"typing_duration":2,"content":{"text":"全都重看一遍吧","parse_mode":null}},{"message_id":"m096","after_start":791,"actor_id":"a_mu","reply_to":null,"typing_duration":2,"content":{"text":"这工程有点大","parse_mode":null}}]}
    script["version"] = "1.0"
    script.pop("chat", None)
    script["script"]["start_at"] = (
        datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(seconds=10)
    ).isoformat()

    from session import session_set

    #Mathis

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
    chat_id = -1004313239881
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
        from session import session_set
        
        operator = {}

        # 随机从 session_set 中选择，形成另外的子集合
        selected_sessions = random.sample(list(session_set.values()), 1)

        selected_sessions[0] = session_set[7]

        # 遍循 selected_sessions
        
        for i, session in enumerate(selected_sessions):
            try:
                operator_length = len(operator)

                operator[(operator_length)] = await HumanBotOperator.login_with_session(
                    session_string=session,
                    api_id=API_ID,
                    api_hash=API_HASH,
                    taobao_bot_username=config.get("taobao_bot_username"),
                )
                #将 operator_opp 添加到 operator 字典中
                # operator[i] = operator_opp
            except Exception as e:
                print(f"Failed to login with session {i} {session}: {e}", flush=True)

            
            # await operator.join_chat("https://t.me/+i5S7P-Dol4dhNzA5")  #加入布吉岛主 1004335920222
            # await operator.join_chat("https://t.me/+iHyXV6FFCQAxN2Ix")  #加入布吉岛
            # https://t.me/+LmR0F1WpnFQ0Y2Ix
        
        
        for i, session in enumerate(operator):
            op = operator[i] 

            # await op.join_chat("+mhqJ-3C93F0zODEx") #桃花林 
            # await op.join_chat("+V-gROBOr4sY2YzVh") #桃花源


            # await op.update_profile(random_name=True)

            # await op.join_chat("https://t.me/+LmR0F1WpnFQ0Y2Ix")  #测试群
        
            
            # await op.send_random_message(chat_id=[-1004335920222, -1004372020134])

            # await op.tracking_message_range(chat=-1004335920222)
            # await op.tracking_message_range(chat=-1004372020134)
            await op.extract(code="/start item_4903",bot_id=8791594127)
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
        # await asyncio.gather(telethon_task)
    finally:
        tasks = [aiogram_task, telethon_task]
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main2())
