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
        # await account_manager.check_phone("+6282127381599")
        # await account_manager.check_phone("+6282127491912")
        # await account_manager.check_phone("+916295379623")

    finally:
        await MySQLPool.close()

async def main_auto_talk() -> None:
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
    
    


    from talk import script 
    # script = {"version":"1.0","script":{"script_id":"first_love_chat_5","title":"初恋","start_at":"2026-09-15T02:20:00+08:00"},"participants":[{"actor_id":"a01","name":"林远","sender_type":"user","sender_id":"a01","language":"zh-CN"},{"actor_id":"a02","name":"周野","sender_type":"user","sender_id":"a02","language":"zh-CN"},{"actor_id":"a03","name":"陈默","sender_type":"user","sender_id":"a03","language":"zh-CN"},{"actor_id":"a04","name":"许嘉","sender_type":"user","sender_id":"a04","language":"zh-CN"},{"actor_id":"a05","name":"沈屿","sender_type":"user","sender_id":"a05","language":"zh-TW"}],"messages":[{"message_id":"m001","after_start":12,"actor_id":"a01","reply_to":null,"typing_duration":2,"content":{"text":"所以你们觉得初恋一定要算正式在一起吗","parse_mode":null}},{"message_id":"m002","after_start":78,"actor_id":"a03","reply_to":null,"typing_duration":2,"content":{"text":"不一定吧","parse_mode":null}},{"message_id":"m003","after_start":145,"actor_id":"a02","reply_to":"m001","typing_duration":4,"content":{"text":"我反而觉得暗恋很久但没在一起，也挺像初恋的","parse_mode":null}},{"message_id":"m004","after_start":213,"actor_id":"a04","reply_to":null,"typing_duration":3,"content":{"text":"嗯……这个定义有点难","parse_mode":null}},{"message_id":"m005","after_start":281,"actor_id":"a05","reply_to":null,"typing_duration":3,"content":{"text":"我以前一直以為初戀就是第一次真的很喜歡一個人","parse_mode":null}},{"message_id":"m006","after_start":350,"actor_id":"a01","reply_to":"m005","typing_duration":3,"content":{"text":"这个我同意","parse_mode":null}},{"message_id":"m007","after_start":420,"actor_id":"a02","reply_to":null,"typing_duration":2,"content":{"text":"而且第一次喜欢人的时候，自己通常特别傻","parse_mode":null}},{"message_id":"m008","after_start":488,"actor_id":"a04","reply_to":"m007","typing_duration":2,"content":{"text":"哈哈哈，确实","parse_mode":null}},{"message_id":"m009","after_start":557,"actor_id":"a03","reply_to":null,"typing_duration":4,"content":{"text":"我那时候连对方多回一个表情都能想半天","parse_mode":null}},{"message_id":"m010","after_start":625,"actor_id":"a05","reply_to":"m009","typing_duration":2,"content":{"text":"這種我懂 😂","parse_mode":null}},{"message_id":"m011","after_start":694,"actor_id":"a01","reply_to":null,"typing_duration":5,"content":{"text":"我第一次喜欢一个人的时候，最明显的感觉是突然很在意自己的形象","parse_mode":null}},{"message_id":"m012","after_start":763,"actor_id":"a04","reply_to":"m011","typing_duration":3,"content":{"text":"这个好真实","parse_mode":null}},{"message_id":"m013","after_start":832,"actor_id":"a02","reply_to":null,"typing_duration":3,"content":{"text":"以前上课前还会照一下镜子","parse_mode":null}},{"message_id":"m014","after_start":900,"actor_id":"a03","reply_to":"m013","typing_duration":2,"content":{"text":"你居然说出来了","parse_mode":null}},{"message_id":"m015","after_start":969,"actor_id":"a05","reply_to":null,"typing_duration":3,"content":{"text":"男生喜歡上別人的時候，好像真的會突然變得很注意細節","parse_mode":null}},{"message_id":"m016","after_start":1038,"actor_id":"a01","reply_to":"m015","typing_duration":3,"content":{"text":"比如？","parse_mode":null}},{"message_id":"m017","after_start":1107,"actor_id":"a05","reply_to":"m016","typing_duration":4,"content":{"text":"比如頭髮、衣服，還有講話的方式","parse_mode":null}},{"message_id":"m018","after_start":1176,"actor_id":"a02","reply_to":null,"typing_duration":2,"content":{"text":"突然开始会装酷","parse_mode":null}},{"message_id":"m019","after_start":1245,"actor_id":"a04","reply_to":"m018","typing_duration":3,"content":{"text":"然后其实心里慌得要死","parse_mode":null}},{"message_id":"m020","after_start":1314,"actor_id":"a03","reply_to":null,"typing_duration":2,"content":{"text":"哈哈","parse_mode":null}},{"message_id":"m021","after_start":1383,"actor_id":"a01","reply_to":null,"typing_duration":4,"content":{"text":"你们第一次心动的时候，会主动吗","parse_mode":null}},{"message_id":"m022","after_start":1452,"actor_id":"a02","reply_to":"m021","typing_duration":2,"content":{"text":"我不会","parse_mode":null}},{"message_id":"m023","after_start":1521,"actor_id":"a03","reply_to":"m021","typing_duration":3,"content":{"text":"看情况","parse_mode":null}},{"message_id":"m024","after_start":1590,"actor_id":"a04","reply_to":"m021","typing_duration":3,"content":{"text":"我应该会先观察很久","parse_mode":null}},{"message_id":"m025","after_start":1659,"actor_id":"a05","reply_to":"m021","typing_duration":4,"content":{"text":"我以前是那種很不敢主動的人","parse_mode":null}},{"message_id":"m026","after_start":1728,"actor_id":"a01","reply_to":"m025","typing_duration":2,"content":{"text":"以前？现在就敢了？","parse_mode":null}},{"message_id":"m027","after_start":1797,"actor_id":"a05","reply_to":"m026","typing_duration":3,"content":{"text":"現在也沒有多厲害啦","parse_mode":null}},{"message_id":"m028","after_start":1866,"actor_id":"a02","reply_to":null,"typing_duration":3,"content":{"text":"我觉得第一次喜欢人的时候，最怕的是被发现","parse_mode":null}},{"message_id":"m029","after_start":1935,"actor_id":"a03","reply_to":"m028","typing_duration":3,"content":{"text":"尤其怕朋友发现","parse_mode":null}},{"message_id":"m030","after_start":2004,"actor_id":"a04","reply_to":null,"typing_duration":2,"content":{"text":"对，自己都还没想明白呢","parse_mode":null}},{"message_id":"m031","after_start":2073,"actor_id":"a01","reply_to":null,"typing_duration":4,"content":{"text":"我当时甚至会故意绕路，就为了多走一会儿","parse_mode":null}},{"message_id":"m032","after_start":2142,"actor_id":"a02","reply_to":"m031","typing_duration":2,"content":{"text":"你这已经很明显了吧","parse_mode":null}},{"message_id":"m033","after_start":2211,"actor_id":"a03","reply_to":null,"typing_duration":2,"content":{"text":"哈哈哈哈","parse_mode":null}},{"message_id":"m034","after_start":2280,"actor_id":"a05","reply_to":"m031","typing_duration":4,"content":{"text":"這種偷偷找機會靠近的感覺，我覺得就是初戀最可愛的地方","parse_mode":null}},{"message_id":"m035","after_start":2349,"actor_id":"a04","reply_to":null,"typing_duration":3,"content":{"text":"可爱归可爱，真的很累","parse_mode":null}},{"message_id":"m036","after_start":2418,"actor_id":"a01","reply_to":"m035","typing_duration":3,"content":{"text":"每天都在猜对方到底什么意思","parse_mode":null}},{"message_id":"m037","after_start":2487,"actor_id":"a02","reply_to":null,"typing_duration":3,"content":{"text":"一个“晚安”都能脑补一整晚","parse_mode":null}},{"message_id":"m038","after_start":2556,"actor_id":"a03","reply_to":"m037","typing_duration":2,"content":{"text":"太真实了","parse_mode":null}},{"message_id":"m039","after_start":2625,"actor_id":"a04","reply_to":null,"typing_duration":3,"content":{"text":"我觉得初恋最容易记住的反而不是结果","parse_mode":null}},{"message_id":"m040","after_start":2694,"actor_id":"a05","reply_to":"m039","typing_duration":4,"content":{"text":"而是一些很小的事情，像是對方第一次叫你的名字","parse_mode":null}},{"message_id":"m041","after_start":2763,"actor_id":"a01","reply_to":"m040","typing_duration":3,"content":{"text":"对","parse_mode":null}},{"message_id":"m042","after_start":2832,"actor_id":"a02","reply_to":null,"typing_duration":3,"content":{"text":"还有第一次一起走回家的路","parse_mode":null}},{"message_id":"m043","after_start":2901,"actor_id":"a03","reply_to":"m042","typing_duration":2,"content":{"text":"这个我有点共鸣","parse_mode":null}},{"message_id":"m044","after_start":2970,"actor_id":"a04","reply_to":null,"typing_duration":4,"content":{"text":"那种路其实也没多特别，但就是会记得","parse_mode":null}},{"message_id":"m045","after_start":3039,"actor_id":"a05","reply_to":null,"typing_duration":3,"content":{"text":"沒錯","parse_mode":null}},{"message_id":"m046","after_start":3108,"actor_id":"a01","reply_to":null,"typing_duration":3,"content":{"text":"你们还记得初恋喜欢的人是什么类型吗","parse_mode":null}},{"message_id":"m047","after_start":3177,"actor_id":"a02","reply_to":"m046","typing_duration":3,"content":{"text":"记得，安静一点的","parse_mode":null}},{"message_id":"m048","after_start":3246,"actor_id":"a03","reply_to":"m046","typing_duration":3,"content":{"text":"我喜欢过一个特别爱笑的","parse_mode":null}},{"message_id":"m049","after_start":3315,"actor_id":"a04","reply_to":"m046","typing_duration":4,"content":{"text":"我以前喜欢的那个人很会照顾别人","parse_mode":null}},{"message_id":"m050","after_start":3384,"actor_id":"a05","reply_to":"m046","typing_duration":4,"content":{"text":"我比較容易被溫柔的人吸引","parse_mode":null}},{"message_id":"m051","after_start":3453,"actor_id":"a01","reply_to":"m050","typing_duration":2,"content":{"text":"温柔这个很难挡","parse_mode":null}},{"message_id":"m052","after_start":3522,"actor_id":"a03","reply_to":null,"typing_duration":3,"content":{"text":"但有时候就是喜欢上了，也说不清为什么","parse_mode":null}},{"message_id":"m053","after_start":3591,"actor_id":"a02","reply_to":"m052","typing_duration":2,"content":{"text":"对","parse_mode":null}},{"message_id":"m054","after_start":3660,"actor_id":"a04","reply_to":null,"typing_duration":3,"content":{"text":"可能就是某一天突然觉得，他跟别人不一样","parse_mode":null}},{"message_id":"m055","after_start":3729,"actor_id":"a05","reply_to":"m054","typing_duration":3,"content":{"text":"然後就完了","parse_mode":null}},{"message_id":"m056","after_start":3798,"actor_id":"a01","reply_to":"m055","typing_duration":2,"content":{"text":"哈哈，完了","parse_mode":null}},{"message_id":"m057","after_start":3867,"actor_id":"a02","reply_to":null,"typing_duration":3,"content":{"text":"我比较想知道，你们有人真的告白成功过吗","parse_mode":null}},{"message_id":"m058","after_start":3936,"actor_id":"a03","reply_to":"m057","typing_duration":2,"content":{"text":"有","parse_mode":null}},{"message_id":"m059","after_start":4005,"actor_id":"a04","reply_to":"m057","typing_duration":3,"content":{"text":"没有","parse_mode":null}},{"message_id":"m060","after_start":4074,"actor_id":"a05","reply_to":"m057","typing_duration":3,"content":{"text":"沒有成功過","parse_mode":null}},{"message_id":"m061","after_start":4143,"actor_id":"a01","reply_to":"m057","typing_duration":3,"content":{"text":"我也没有","parse_mode":null}},{"message_id":"m062","after_start":4212,"actor_id":"a02","reply_to":null,"typing_duration":3,"content":{"text":"那陈默你怎么成功的","parse_mode":null}},{"message_id":"m063","after_start":4281,"actor_id":"a03","reply_to":"m062","typing_duration":4,"content":{"text":"其实也没什么，就是有一天觉得再不说就会一直憋着","parse_mode":null}},{"message_id":"m064","after_start":4350,"actor_id":"a04","reply_to":null,"typing_duration":3,"content":{"text":"结果呢","parse_mode":null}},{"message_id":"m065","after_start":4419,"actor_id":"a03","reply_to":"m064","typing_duration":3,"content":{"text":"在一起了一阵子，后来还是分开了","parse_mode":null}},{"message_id":"m066","after_start":4488,"actor_id":"a05","reply_to":null,"typing_duration":4,"content":{"text":"那你現在還會想起他嗎","parse_mode":null}},{"message_id":"m067","after_start":4557,"actor_id":"a03","reply_to":"m066","typing_duration":3,"content":{"text":"偶尔吧，不难受，就是会想起","parse_mode":null}},{"message_id":"m068","after_start":4626,"actor_id":"a01","reply_to":"m067","typing_duration":2,"content":{"text":"感觉这才是放下了","parse_mode":null}},{"message_id":"m069","after_start":4695,"actor_id":"a02","reply_to":null,"typing_duration":3,"content":{"text":"不是完全忘掉才叫放下","parse_mode":null}},{"message_id":"m070","after_start":4764,"actor_id":"a04","reply_to":"m069","typing_duration":2,"content":{"text":"嗯","parse_mode":null}},{"message_id":"m071","after_start":4833,"actor_id":"a05","reply_to":null,"typing_duration":4,"content":{"text":"我覺得初戀比較像是一個很早出現的記號","parse_mode":null}},{"message_id":"m072","after_start":4902,"actor_id":"a01","reply_to":"m071","typing_duration":3,"content":{"text":"这个说法挺好","parse_mode":null}},{"message_id":"m073","after_start":4971,"actor_id":"a02","reply_to":null,"typing_duration":4,"content":{"text":"不过我现在回头看，会觉得以前的自己真的很容易紧张","parse_mode":null}},{"message_id":"m074","after_start":5040,"actor_id":"a03","reply_to":"m073","typing_duration":2,"content":{"text":"现在也一样吧","parse_mode":null}},{"message_id":"m075","after_start":5109,"actor_id":"a02","reply_to":"m074","typing_duration":2,"content":{"text":"……你别拆穿","parse_mode":null}},{"message_id":"m076","after_start":5178,"actor_id":"a04","reply_to":null,"typing_duration":3,"content":{"text":"哈哈哈哈","parse_mode":null}},{"message_id":"m077","after_start":5247,"actor_id":"a01","reply_to":null,"typing_duration":4,"content":{"text":"其实喜欢一个人的时候紧张也挺正常的","parse_mode":null}},{"message_id":"m078","after_start":5316,"actor_id":"a05","reply_to":"m077","typing_duration":3,"content":{"text":"而且越在意越容易裝得不在意","parse_mode":null}},{"message_id":"m079","after_start":5385,"actor_id":"a03","reply_to":"m078","typing_duration":3,"content":{"text":"这句话有点扎心","parse_mode":null}},{"message_id":"m080","after_start":5454,"actor_id":"a04","reply_to":null,"typing_duration":3,"content":{"text":"有时候还故意晚回消息","parse_mode":null}},{"message_id":"m081","after_start":5523,"actor_id":"a01","reply_to":"m080","typing_duration":3,"content":{"text":"然后盯着手机等对方回","parse_mode":null}},{"message_id":"m082","after_start":5592,"actor_id":"a02","reply_to":"m081","typing_duration":2,"content":{"text":"你们怎么都知道","parse_mode":null}},{"message_id":"m083","after_start":5661,"actor_id":"a05","reply_to":null,"typing_duration":3,"content":{"text":"因為大家都差不多啦","parse_mode":null}},{"message_id":"m084","after_start":5730,"actor_id":"a03","reply_to":null,"typing_duration":4,"content":{"text":"初恋这种东西，估计谁都逃不过一点笨拙","parse_mode":null}},{"message_id":"m085","after_start":5799,"actor_id":"a04","reply_to":"m084","typing_duration":2,"content":{"text":"同意","parse_mode":null}},{"message_id":"m086","after_start":5868,"actor_id":"a01","reply_to":null,"typing_duration":3,"content":{"text":"如果再来一次，你们会勇敢一点吗","parse_mode":null}},{"message_id":"m087","after_start":5937,"actor_id":"a02","reply_to":"m086","typing_duration":2,"content":{"text":"会","parse_mode":null}},{"message_id":"m088","after_start":6006,"actor_id":"a03","reply_to":"m086","typing_duration":3,"content":{"text":"会早点说吧","parse_mode":null}},{"message_id":"m089","after_start":6075,"actor_id":"a04","reply_to":"m086","typing_duration":3,"content":{"text":"我可能还是会犹豫","parse_mode":null}},{"message_id":"m090","after_start":6144,"actor_id":"a05","reply_to":"m086","typing_duration":4,"content":{"text":"我應該會多勇敢一點點","parse_mode":null}},{"message_id":"m091","after_start":6213,"actor_id":"a01","reply_to":"m090","typing_duration":3,"content":{"text":"一点点也很好","parse_mode":null}},{"message_id":"m092","after_start":6282,"actor_id":"a02","reply_to":null,"typing_duration":3,"content":{"text":"至少不会一直猜","parse_mode":null}},{"message_id":"m093","after_start":6351,"actor_id":"a03","reply_to":"m092","typing_duration":2,"content":{"text":"对","parse_mode":null}},{"message_id":"m094","after_start":6420,"actor_id":"a04","reply_to":null,"typing_duration":3,"content":{"text":"不过现在想想，那种小心翼翼也挺珍贵的","parse_mode":null}},{"message_id":"m095","after_start":6489,"actor_id":"a05","reply_to":"m094","typing_duration":3,"content":{"text":"嗯，因為那時候什麼都是第一次","parse_mode":null}},{"message_id":"m096","after_start":6558,"actor_id":"a01","reply_to":null,"typing_duration":4,"content":{"text":"第一次等消息，第一次因为一句话开心半天","parse_mode":null}},{"message_id":"m097","after_start":6627,"actor_id":"a02","reply_to":"m096","typing_duration":2,"content":{"text":"第一次失眠","parse_mode":null}},{"message_id":"m098","after_start":6696,"actor_id":"a03","reply_to":"m097","typing_duration":2,"content":{"text":"第一次发现自己原来这么在乎一个人","parse_mode":null}},{"message_id":"m099","after_start":6765,"actor_id":"a04","reply_to":null,"typing_duration":3,"content":{"text":"你们突然说得好认真","parse_mode":null}},{"message_id":"m100","after_start":6834,"actor_id":"a05","reply_to":"m099","typing_duration":2,"content":{"text":"剛好聊到這裡嘛","parse_mode":null}},{"message_id":"m101","after_start":6903,"actor_id":"a01","reply_to":null,"typing_duration":3,"content":{"text":"哈哈，差点以为在上情感课","parse_mode":null}},{"message_id":"m102","after_start":6972,"actor_id":"a02","reply_to":"m101","typing_duration":2,"content":{"text":"那我先下课","parse_mode":null}},{"message_id":"m103","after_start":7041,"actor_id":"a03","reply_to":"m102","typing_duration":2,"content":{"text":"老师不同意","parse_mode":null}},{"message_id":"m104","after_start":7110,"actor_id":"a04","reply_to":null,"typing_duration":2,"content":{"text":"哈哈哈","parse_mode":null}},{"message_id":"m105","after_start":7179,"actor_id":"a05","reply_to":null,"typing_duration":3,"content":{"text":"我覺得這群才剛認識，居然已經聊到初戀了","parse_mode":null}},{"message_id":"m106","after_start":7248,"actor_id":"a01","reply_to":"m105","typing_duration":3,"content":{"text":"陌生人反而比较好聊吧","parse_mode":null}},{"message_id":"m107","after_start":7317,"actor_id":"a02","reply_to":"m106","typing_duration":3,"content":{"text":"不用怕被熟人笑","parse_mode":null}},{"message_id":"m108","after_start":7386,"actor_id":"a03","reply_to":null,"typing_duration":3,"content":{"text":"确实","parse_mode":null}},{"message_id":"m109","after_start":7455,"actor_id":"a04","reply_to":null,"typing_duration":3,"content":{"text":"而且有些事说出来以后，好像也没那么不好意思了","parse_mode":null}},{"message_id":"m110","after_start":7524,"actor_id":"a05","reply_to":"m109","typing_duration":3,"content":{"text":"對","parse_mode":null}},{"message_id":"m111","after_start":7593,"actor_id":"a01","reply_to":null,"typing_duration":4,"content":{"text":"那最后一个问题，你们还会期待下一次初恋吗","parse_mode":null}},{"message_id":"m112","after_start":7662,"actor_id":"a02","reply_to":"m111","typing_duration":2,"content":{"text":"初恋不能有下一次吧","parse_mode":null}},{"message_id":"m113","after_start":7731,"actor_id":"a03","reply_to":"m112","typing_duration":3,"content":{"text":"他说的是下一次喜欢人啦","parse_mode":null}},{"message_id":"m114","after_start":7800,"actor_id":"a02","reply_to":"m113","typing_duration":2,"content":{"text":"哦哦","parse_mode":null}},{"message_id":"m115","after_start":7869,"actor_id":"a04","reply_to":"m111","typing_duration":3,"content":{"text":"会期待啊，不然呢","parse_mode":null}},{"message_id":"m116","after_start":7938,"actor_id":"a05","reply_to":"m111","typing_duration":3,"content":{"text":"會吧，還是希望遇到一個讓自己很想靠近的人","parse_mode":null}},{"message_id":"m117","after_start":8007,"actor_id":"a01","reply_to":"m116","typing_duration":3,"content":{"text":"这个答案不错","parse_mode":null}},{"message_id":"m118","after_start":8076,"actor_id":"a03","reply_to":null,"typing_duration":3,"content":{"text":"我觉得不用急","parse_mode":null}},{"message_id":"m119","after_start":8145,"actor_id":"a04","reply_to":"m118","typing_duration":2,"content":{"text":"对，慢慢来","parse_mode":null}},{"message_id":"m120","after_start":8214,"actor_id":"a05","reply_to":null,"typing_duration":3,"content":{"text":"慢慢來也很好","parse_mode":null}},{"message_id":"m121","after_start":8283,"actor_id":"a01","reply_to":null,"typing_duration":3,"content":{"text":"行，那今天这堂课真的下课了","parse_mode":null}},{"message_id":"m122","after_start":8352,"actor_id":"a02","reply_to":"m121","typing_duration":2,"content":{"text":"散会","parse_mode":null}},{"message_id":"m123","after_start":8421,"actor_id":"a03","reply_to":null,"typing_duration":2,"content":{"text":"哈哈","parse_mode":null}},{"message_id":"m124","after_start":8490,"actor_id":"a04","reply_to":null,"typing_duration":2,"content":{"text":"晚点见","parse_mode":null}},{"message_id":"m125","after_start":8559,"actor_id":"a05","reply_to":null,"typing_duration":2,"content":{"text":"晚點聊","parse_mode":null}}]}
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
    chat_id = -1004335920222
    # chat_id = -1004303617422
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
        session_rows = await MySQLPool.fetchall(
            "SELECT `bot_token` FROM `bot` "
            "WHERE check_group=1 ",
        
            error_tag="userbot.random_session_tokens",
        )
        
        if not session_rows:
            raise RuntimeError(
                "从数据库中获取到的 session_rows 为空"
            )
        if len(session_rows) < 1:
            raise RuntimeError(
                f"数据库中的 bot_token 数量不足：需要 1 个，实际只有 {len(session_rows)} 个"
            )
       

        session_set = {
            index: str(row["bot_token"]).strip()
            for index, row in enumerate(session_rows)
        }

        operator = {}

        # 随机从 session_set 中选择，形成另外的子集合
        selected_sessions = random.sample(list(session_set.values()), len(session_set))

        # selected_sessions[0] = session_set[7]

        # 遍循 selected_sessions
        # selected_sessions = list(session_set.values())

        for i, session in enumerate(selected_sessions):
            try:
                operator_length = len(operator)

                op = await HumanBotOperator.login_with_session(
                    session_string=session,
                    api_id=API_ID,
                    api_hash=API_HASH,
                    taobao_bot_username=config.get("taobao_bot_username"),
                )
                operator[(operator_length)] = op
                #将 operator_opp 添加到 operator 字典中
                # operator[i] = operator_opp
                # await op.join_chat("https://t.me/+_Pz9_6udznFlMDhi") #玉树花

                # await op.join_chat("https://t.me/+HYvGBwaTSUEyYzkx")  #正太方舟
                await op.client.send_message("@posterre_bot", "/checkin")      
                # await op.join_chat("https://t.me/+LmR0F1WpnFQ0Y2Ix")
                # await op.client.send_message("@yunupan1bot", "/start") 
            except Exception as e:
                print(f"Failed to login with session {i} {session}: {e}", flush=True)

        

            # https://t.me/+LmR0F1WpnFQ0Y2Ix
        
        cset = {}


        cset_pxm_27491912={"🪜📔🏣🍸🧂🐍😩📆","🪜📔🏣🍸🧂🐍😩📆","🌛🎣😀🌕🍌🤢🔨🥗","📱💳🚞🔫🥵📰🥎🐙","🐸🛠🌆🚟🩰😌🤓🍺","🌛🔋🐗📆🎂📆🎭🤫","😃🤐🦉🥌🧿🍺🦙🧽"}
        cset_ow_4254 ={"🎉🛠🎰🐦🐉🏡🔎🥒","🦕🖨🍳🍱🐤💫🚘🍲","🚽🦔🔎🐄🍑🐇🍮🏡","🦁🐙🔦🐍🪳💫🦔🌌","😊📡🎢🐉🐍📔🚝😊","🎇😽🏵🍱🧆🐨🫐😴","🥘🎣🎭🍲🛤🚍🍟🎚","🤹🍋🐦🌈🔫🎂🎣🏜"}
        cset_gayne_7972120149={"📐😊🎻🧿😓🐜😀😈","🌚🐼🧹🚘🐦🩰🎫🚽","😮🛺📐🤫📐🔦🌙🪙","😳🎭🌡🛖🐤🤮💌🛺","🚝🐦🍳😽😃🐊🐭😺"}
        cset_guojin={"🚑🌸🍌🎯🛏🌌📡🌇","🥖😂🏒🏜🛁🐀🧽🌇","🪳🥘🔖🍲😂🥬🚍🚟"}
        cset_light={"🪜🐺😋🦕🛡🐜🚽🦌","🌶🎂🐗🌌🗼🐼🍣🦕","🐤🚝🥋😀🧂🐙🔫🐍","🔪🪵😬🧺🍺🌒😃🧺","🍸🎰🧂🤕🎖🪙🤹😌"}
        cset = cset_light
        # cset[1]="🤫🏵😬🥪🎭🏫🎣🥣"
        # cset[2]="🌕🛖🔨🫔🐪🐄🎡🧆"
        # cset[3]="📰🏒😉😠🔨📺🐗🚤"
        # cset[4]="🐱🎢🚅🙊🌠😆🦊🚆"
        # cset[5]="🌇🚞🖨😩🌴🚑🗼🔫"
        # cset[6]="🏘🌚🚘🛺🔨🏢🐄🖨"
        # cset[7]="🍜🛤🥨🌯🫐🔫🛡😴"

        # for code in cset:
        #     for i, op in operator.items():
        #         print(f"code={code} i={i}", flush=True)
        #         r = await op.extract(code=code, bot_id=BJD_CODE_BOT_ID, ask_like=True)

        #         await asyncio.sleep(random.randint(3, 5))

        for t in range(10000):  # Example range, adjust as needed
            for i, session in enumerate(operator):
                op = operator[i] 

                # await op.join_chat("https://t.me/+i5S7P-Dol4dhNzA5")  #加入布吉岛主 1004335920222
                # await op.join_chat("https://t.me/+iHyXV6FFCQAxN2Ix")  #加入布吉岛
                # await op.join_chat("+mhqJ-3C93F0zODEx") #桃花林 
                # await op.join_chat("+V-gROBOr4sY2YzVh") #桃花源
                # await op.join_chat("https://t.me/+PmSBya7t51JmOTNh") #unbrella
                # await op.join_chat("https://t.me/+LmR0F1WpnFQ0Y2Ix")  #测试群
             
                
                # await op.update_profile(random_name=True)
                # await op.send_random_message(chat_id=[-1004335920222, -1004372020134])

                await op.tracking_message_range(chat=-1004335920222)
                await op.tracking_message_range(chat=-1004372020134)
                try:
                    me = await op.client.get_me()
                    display_name = (
                        getattr(me, "first_name", None)
                        or getattr(me, "username", None)
                        or f"ID:{getattr(me, 'id', i)}"
                    )
                    print(
                        f"\n第 {t + 1} 轮、账号 {i}（{display_name}）开始提取...",
                        flush=True,
                    )
                    await op.extract(ask_like=True)

                except TimeoutError as exc:
                    print(
                        f"第 {t + 1} 轮、账号 {i} 提取超时，"
                        f"跳过本次并继续：{exc}",
                        flush=True,
                    )
                    continue
                # for i in range(4156, 4164):  # 从 4900 往下降到 4800
                #     await op.extract(secret_id=i)
                #     await asyncio.sleep(random.randint(10, 25))
                # await op.routine_insert()
                # while True:


                

                # sleep_time = random.randint(10, 25)
                # await asyncio.sleep(sleep_time)
                # await op.send_first_video_to_bot(source_chat=7613284106,target_bot="@di5k7bot",search_limit=5000)




                sleep_time = random.randint(3, 7)
                print(f"==>Sleeping for {sleep_time} seconds before next operation.", flush=True)
                await asyncio.sleep(sleep_time)
        print(f"✅ Completed", flush=True)
        
        for i, session in enumerate(operator):
            op = operator[i] 
            await op.disconnect()
            # await account_manager.check_all_userbot(config)
            # await account_manager.rec_new_account(
            #     phone_number="+15809565862",
            #     pw2fa="z4422404",
            # )
            # await account_manager.check_phone("+18157706388")
        print("所有操作已完成，正在断开连接...", flush=True)
    finally:
        await MySQLPool.close()
        return
        
def configure_mysql_pool(config: dict) -> None:
    """使用统一配置初始化 MySQLPool。"""
    MySQLPool.configure(
        host=config.get("db_host", os.getenv("MYSQL_DB_HOST", "localhost")),
        user=config.get("db_user", os.getenv("MYSQL_DB_USER", "")),
        password=config.get("db_password", os.getenv("MYSQL_DB_PASSWORD", "")),
        database=config.get("db_name", os.getenv("MYSQL_DB_NAME", "")),
        port=int(config.get("db_port", os.getenv("MYSQL_DB_PORT", 3306))),
    )

async def main() -> None:
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
    aiogram_connected_task = asyncio.create_task(
        aiogram_operator.connected_event.wait(),
        name="wait-aiogram-connected",
    )
    telethon_task = None

    try:
        done, _ = await asyncio.wait(
            (aiogram_task, aiogram_connected_task),
            return_when=asyncio.FIRST_COMPLETED,
        )
        if aiogram_task in done:
            # Aiogram 在连接成功前异常结束，直接向上传递异常，避免永久等待。
            await aiogram_task

        await aiogram_connected_task
        print("Aiogram Bot 已确认连接，正在启动 Telethon...", flush=True)
        # print(f"config: {config}")
        telethon_task = asyncio.create_task(
            run_telethon_bot(config, configure_mysql=False),
            name="telethon-user-flow",
        )
        await asyncio.gather(aiogram_task, telethon_task)
    finally:
        tasks = [aiogram_task, aiogram_connected_task]
        if telethon_task is not None:
            tasks.append(telethon_task)
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    async def _run_all() -> None:
        await main_auto_talk()
        await main()

    asyncio.run(_run_all())
