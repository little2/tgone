# bounty.py
# 主程式（aiogram v3 + asyncpg + PostgreSQL）
# 依赖：
#   - tgone_pgsql.py  (PGPool)
#   - bounty_repo.py  (BountyRepo)
#   - bounty_config.py (cfg 常数/配置，含 .env 读取与 validate)

import asyncio
import logging
import time
from typing import List, Tuple

from aiogram import Bot, Dispatcher, Router, F
from aiogram.enums import ParseMode
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    InputMediaPhoto, InputMediaVideo,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage

import bounty_config as cfg
from tgone_pgsql import PGPool
from bounty_repo import BountyRepo


def now_ts() -> int:
    return int(time.time())


# -----------------------------
# Fake Points Service (replace later)
# -----------------------------

class PointsError(Exception):
    pass


class PointsService:
    @staticmethod
    async def deduct(user_id: int, amount: int, memo: str) -> None:
        if amount <= 0:
            raise PointsError("amount must be > 0")
        # fake ok

    @staticmethod
    async def transfer(from_uid: int, to_uid: int, amount: int, memo: str) -> None:
        if amount <= 0:
            raise PointsError("amount must be > 0")
        # fake ok

    @staticmethod
    async def refund(to_uid: int, amount: int, memo: str) -> None:
        if amount <= 0:
            raise PointsError("amount must be > 0")
        # fake ok


# -----------------------------
# Telegram helpers: album sending
# -----------------------------

async def send_protected_album(bot: Bot, chat_id: int, items: List[Tuple[str, str]]):
    """
    审核中发送真实媒体（protect_content=True）：
    - photo/video => send_media_group（最多10个一组）
    - document => send_document（相簿不支持 document）
    """
    medias: List[InputMediaPhoto | InputMediaVideo] = []
    docs: List[str] = []

    for ft, fid in items:
        if ft == "photo":
            medias.append(InputMediaPhoto(media=fid))
        elif ft == "video":
            medias.append(InputMediaVideo(media=fid))
        else:
            docs.append(fid)

    for i in range(0, len(medias), 10):
        batch = medias[i:i + 10]
        if batch:
            await bot.send_media_group(chat_id, batch, protect_content=True)

    for fid in docs:
        await bot.send_document(chat_id, fid, protect_content=True)


async def send_transferable_copy(bot: Bot, chat_id: int, bounty_user_id: int):
    """
    accept / auto-accept 后，把同一批资源再发一次（protect_content=False）使其可转发
    """
    items = await BountyRepo.list_items(bounty_user_id)
    for ft, fid in items:
        if ft == "photo":
            await bot.send_photo(chat_id, fid, protect_content=False)
        elif ft == "video":
            await bot.send_video(chat_id, fid, protect_content=False)
        else:
            await bot.send_document(chat_id, fid, protect_content=False)


# -----------------------------
# Keyboards
# -----------------------------

def kb_board_view(bounty_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="查看详情", callback_data=f"bounty:view:{bounty_id}")]
    ])


def kb_view_actions(bounty_id: int, status: int, is_creator: bool) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    if status == cfg.B1_OPEN:
        rows.append([InlineKeyboardButton(text="我要圆梦", callback_data=f"bounty:claim:{bounty_id}")])
    if status == cfg.B9_DONE and is_creator:
        rows.append([InlineKeyboardButton(text="申请退款并关结", callback_data=f"bounty:refund:{bounty_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_review_actions(bounty_id: int, review_chat_id: int, review_msg_id: int) -> InlineKeyboardMarkup:
    # reject callback 携带 review_chat_id/review_msg_id（不入库）
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="接受", callback_data=f"bounty:accept:{bounty_id}"),
            InlineKeyboardButton(text="拒绝", callback_data=f"bounty:reject:{bounty_id}:{review_chat_id}:{review_msg_id}"),
        ]
    ])


def kb_hunter_after_reject(bounty_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="申请仲裁", callback_data=f"bounty:arbit:{bounty_id}")]
    ])


# -----------------------------
# FSM: /wish
# -----------------------------

class WishFSM(StatesGroup):
    content = State()
    media = State()
    bonus = State()


router = Router()


@router.message(F.text == "/start")
async def start(msg: Message):
    await msg.answer(
        "许愿池机器人已启动。\n\n"
        "指令：\n"
        "/wish  新增许愿\n"
        "/submit  圆梦者提交完成（资源提交中状态）\n"
        "/help  帮助"
    )


@router.message(F.text == "/help")
async def help_cmd(msg: Message):
    await msg.answer(
        "流程：\n"
        "1) /wish 许愿并上墙（发布即扣分）\n"
        "2) 他人点“我要圆梦”领取后上传资源（多条）\n"
        "3) 圆梦者发送 /submit 提交\n"
        "4) 许愿者私聊中接受/拒绝（审核中媒体 protect_content=True）\n"
        "5) 14天无人圆梦自动结束（状态9），许愿者可申请退款并关结（状态10）"
    )


@router.message(F.text == "/wish")
async def wish_start(msg: Message, state: FSMContext):
    await state.clear()
    await state.set_state(WishFSM.content)
    await msg.answer("请输入许愿描述（bounty_content）：")


@router.message(WishFSM.content)
async def wish_set_content(msg: Message, state: FSMContext):
    text = (msg.text or "").strip()
    if not text:
        await msg.answer("请输入有效文字描述。")
        return
    await state.update_data(bounty_content=text)
    await state.set_state(WishFSM.media)
    await msg.answer("可选：上传示意媒体（photo/video/document）。新媒体会覆盖旧媒体。完成后输入 /next 进入积分设置。")


# ✅ wish_set_media：覆盖式更新
@router.message(WishFSM.media, F.content_type.in_({"photo", "video", "document"}))
async def wish_set_media(msg: Message, state: FSMContext):
    if msg.photo:
        p = msg.photo[-1]
        await state.update_data(file_id=p.file_id, file_unique_id=p.file_unique_id, file_type="photo")
    elif msg.video:
        v = msg.video
        await state.update_data(file_id=v.file_id, file_unique_id=v.file_unique_id, file_type="video")
    else:
        d = msg.document
        await state.update_data(file_id=d.file_id, file_unique_id=d.file_unique_id, file_type="document")

    await msg.answer("已更新示意媒体（新上传将覆盖旧的）。输入 /next 进入积分设置。")


@router.message(WishFSM.media, F.text == "/next")
async def wish_next(msg: Message, state: FSMContext):
    await state.set_state(WishFSM.bonus)
    await msg.answer("请输入悬赏积分 bonus（正整数）：")


@router.message(WishFSM.bonus)
async def wish_publish(msg: Message, state: FSMContext, bot: Bot):
    raw = (msg.text or "").strip()
    if not raw.isdigit():
        await msg.answer("请输入正整数积分。")
        return

    bonus = int(raw)
    if bonus <= 0:
        await msg.answer("积分必须大于0。")
        return

    data = await state.get_data()
    bounty_content = data.get("bounty_content")
    file_id = data.get("file_id")
    file_unique_id = data.get("file_unique_id")
    file_type = data.get("file_type")

    # 1) 发布即扣分（占位）
    try:
        await PointsService.deduct(msg.from_user.id, bonus, memo="bounty publish deduct")
    except Exception as e:
        await msg.answer(f"扣分失败：{e}")
        return

    # 2) DB
    bounty_id = await BountyRepo.create_bounty(
        creator_id=msg.from_user.id,
        bonus=bonus,
        bounty_content=bounty_content,
        file_id=file_id,
        file_unique_id=file_unique_id,
        file_type=file_type,
        bot_name=bot.username if bot.username else None
    )

    # 3) 上墙
    board_msg = await bot.send_message(
        cfg.BOARD_CHAT_ID,
        f"🧞 新许愿 #{bounty_id}\n悬赏：{bonus} 积分\n（点击查看详情参与圆梦）",
        reply_markup=kb_board_view(bounty_id)
    )
    await BountyRepo.set_board_message(bounty_id, cfg.BOARD_CHAT_ID, board_msg.message_id)

    await msg.answer(f"许愿已发布，上墙编号 #{bounty_id}")
    await state.clear()


# -----------------------------
# View / Claim
# -----------------------------

@router.callback_query(F.data.startswith("bounty:view:"))
async def bounty_view(cb: CallbackQuery):
    bounty_id = int(cb.data.split(":")[2])
    b = await BountyRepo.get_bounty(bounty_id)
    if not b:
        await cb.answer("许愿不存在")
        return

    status = int(b["bounty_status"])
    creator_id = int(b["creator_id"])
    is_creator = (cb.from_user.id == creator_id)

    text = (
        f"许愿 #{bounty_id}\n"
        f"状态：{status}\n"
        f"悬赏：{int(b['bonus'])}\n"
        f"内容：{b['bounty_content'] or '(无)'}"
    )
    await cb.message.answer(text, reply_markup=kb_view_actions(bounty_id, status, is_creator=is_creator))
    await cb.answer()


@router.callback_query(F.data.startswith("bounty:claim:"))
async def bounty_claim(cb: CallbackQuery):
    bounty_id = int(cb.data.split(":")[2])
    uid = cb.from_user.id

    bounty_user_id = await BountyRepo.claim_bounty(
        bounty_id=bounty_id,
        hunter_id=uid,
        due_ts=now_ts() + cfg.CLAIM_TIMEOUT
    )
    if bounty_user_id <= 0:
        await cb.answer("该许愿正在被圆梦或不可领取")
        return

    await cb.message.answer(
        f"你已领取许愿 #{bounty_id}。\n"
        f"请上传资源（photo/video/document，可多条），完成后发送 /submit 提交。"
    )
    await cb.answer("领取成功")


# -----------------------------
# Hunter upload items (status=7)
# -----------------------------

@router.message(F.content_type.in_({"photo", "video", "document"}))
async def hunter_upload_item(msg: Message, bot: Bot):
    uid = msg.from_user.id
    b = await BountyRepo.get_current_submitting_bounty_by_hunter(uid)
    if not b:
        return

    bounty_user_id = int(b["current_bounty_user_id"])

    if msg.photo:
        p = msg.photo[-1]
        file_id, file_unique_id, file_type = p.file_id, p.file_unique_id, "photo"
    elif msg.video:
        v = msg.video
        file_id, file_unique_id, file_type = v.file_id, v.file_unique_id, "video"
    else:
        d = msg.document
        file_id, file_unique_id, file_type = d.file_id, d.file_unique_id, "document"

    await BountyRepo.add_bounty_item(
        bounty_user_id=bounty_user_id,
        bot_name=bot.username if bot.username else None,
        file_unique_id=file_unique_id,
        file_id=file_id,
        file_type=file_type,
    )


@router.message(F.text == "/submit")
async def hunter_submit(msg: Message, bot: Bot):
    uid = msg.from_user.id

    result = await BountyRepo.submit_to_review(
        hunter_id=uid,
        review_due_ts=now_ts() + cfg.REVIEW_TIMEOUT
    )
    if not result:
        await msg.answer("你当前没有处于“资源提交中(7)”的许愿。")
        return

    if isinstance(result, tuple) and len(result) == 4 and result[0] == "NO_ITEMS":
        _, bounty_id, _, _ = result
        await msg.answer(f"你还没有上传任何资源，先上传后再 /submit。（许愿 #{bounty_id}）")
        return

    bounty_id, creator_id, bounty_user_id = result  # type: ignore[misc]

    # ✅ 审核中：相簿批量发送 protect_content=True
    items = await BountyRepo.list_items(bounty_user_id)
    await send_protected_album(bot, creator_id, items)

    # 验收按钮消息（reject callback 内含 chat_id/msg_id）
    review_msg = await bot.send_message(
        creator_id,
        f"【审核中】许愿 #{bounty_id}\n请验收圆梦者提交的资源："
    )
    await bot.edit_message_reply_markup(
        creator_id,
        review_msg.message_id,
        reply_markup=kb_review_actions(bounty_id, review_chat_id=creator_id, review_msg_id=review_msg.message_id)
    )

    await msg.answer(f"已提交许愿 #{bounty_id}，等待许愿者验收。")


# -----------------------------
# Accept / Reject / Arbit / Refund
# -----------------------------

@router.callback_query(F.data.startswith("bounty:accept:"))
async def bounty_accept(cb: CallbackQuery, bot: Bot):
    bounty_id = int(cb.data.split(":")[2])
    creator_id = cb.from_user.id

    ret = await BountyRepo.accept_bounty(bounty_id=bounty_id, creator_id=creator_id)
    if not ret:
        await cb.answer("不可操作")
        return

    hunter_id, bonus, bounty_user_id = ret

    # payout: SYSTEM -> hunter（占位）
    try:
        await PointsService.transfer(cfg.SYSTEM_UID, hunter_id, bonus, memo=f"bounty#{bounty_id} payout")
    except Exception as e:
        await cb.answer(f"结算失败：{e}")
        return

    # resend transferable copy
    await send_transferable_copy(bot, creator_id, bounty_user_id)

    try:
        await bot.send_message(creator_id, f"已接受。许愿 #{bounty_id} 已结束（状态9）。")
        await bot.send_message(hunter_id, f"圆梦成功：许愿 #{bounty_id} 已结算 {bonus} 积分。")
    except Exception:
        pass

    await cb.answer("已接受")


@router.callback_query(F.data.startswith("bounty:reject:"))
async def bounty_reject(cb: CallbackQuery, bot: Bot):
    # bounty:reject:<bounty_id>:<chat_id>:<msg_id>
    parts = cb.data.split(":")
    if len(parts) < 5:
        await cb.answer("参数错误")
        return

    bounty_id = int(parts[2])
    review_chat_id = int(parts[3])
    review_msg_id = int(parts[4])
    creator_id = cb.from_user.id

    ret = await BountyRepo.reject_bounty(
        bounty_id=bounty_id,
        creator_id=creator_id,
        return_due_ts=now_ts() + cfg.RETURN_TIMEOUT
    )
    if not ret:
        await cb.answer("不可操作")
        return

    hunter_id, _bounty_user_id = ret

    try:
        await bot.delete_message(review_chat_id, review_msg_id)
    except Exception:
        pass

    try:
        await bot.send_message(
            hunter_id,
            f"许愿 #{bounty_id} 被拒绝，进入退回中（状态3）。你可在1天内申请仲裁。",
            reply_markup=kb_hunter_after_reject(bounty_id)
        )
    except Exception:
        pass

    await cb.answer("已拒绝")


@router.callback_query(F.data.startswith("bounty:arbit:"))
async def bounty_arbit(cb: CallbackQuery, bot: Bot):
    bounty_id = int(cb.data.split(":")[2])
    hunter_id = cb.from_user.id

    ok = await BountyRepo.set_arbitration(bounty_id=bounty_id, hunter_id=hunter_id)
    if not ok:
        await cb.answer("当前不可仲裁")
        return

    for admin_id in cfg.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"【仲裁请求】许愿 #{bounty_id} 进入仲裁中（状态4）。")
        except Exception:
            pass

    await cb.answer("已申请仲裁")


@router.callback_query(F.data.startswith("bounty:refund:"))
async def bounty_refund(cb: CallbackQuery):
    bounty_id = int(cb.data.split(":")[2])
    uid = cb.from_user.id

    res = await BountyRepo.refund_and_close(bounty_id=bounty_id, creator_id=uid)
    if res[0] == "NOT_FOUND":
        await cb.answer("许愿不存在")
        return
    if res[0] == "NO_PERM":
        await cb.answer("无权限")
        return
    if res[0] == "BAD_STATUS":
        await cb.answer(f"当前状态不可退款（需状态9，当前={res[1]}）")
        return

    _, refund_amount, fee = res  # type: ignore[misc]

    try:
        await PointsService.refund(uid, refund_amount, memo=f"bounty#{bounty_id} refund fee={fee}")
    except Exception as e:
        await cb.answer(f"退款失败：{e}")
        return

    await cb.message.answer(f"已退款并关结（状态10）。退还 {refund_amount}，手续费 {fee}。")
    await cb.answer("已退款")


# -----------------------------
# Timeout Worker
# -----------------------------

async def auto_accept_bounty(bot: Bot, bounty_id: int):
    """
    status=2 超时 => 自动接受：
    - 状态 -> 9
    - 结算 SYSTEM -> hunter（占位）
    - 再发一次可转发副本（protect_content=False）
    """
    res = await BountyRepo.timeout_review_auto_accept(bounty_id=bounty_id)
    if not res:
        return

    creator_id, hunter_id, bonus, bounty_user_id = res

    if hunter_id is not None:
        try:
            await PointsService.transfer(cfg.SYSTEM_UID, hunter_id, bonus, memo=f"bounty#{bounty_id} auto payout")
        except Exception:
            pass

    try:
        await send_transferable_copy(bot, creator_id, bounty_user_id)
    except Exception:
        pass

    try:
        await bot.send_message(creator_id, f"许愿 #{bounty_id} 超时未审核，系统已自动接受并结束（状态9）。")
        if hunter_id is not None:
            await bot.send_message(hunter_id, f"许愿 #{bounty_id} 超时自动接受，已结算 {bonus} 积分。")
    except Exception:
        pass


async def bounty_timeout_worker(bot: Bot):
    """
    - 14天无人圆梦：status 1 -> 9
    - due_timestamp 超时处理：
        * 7 -> 8（留痕）-> 1（重开）
        * 2 -> 自动接受 -> 9
        * 3 -> 1（重开）
    """
    while True:
        try:
            # 14天无人领取/圆梦 => 1 -> 9
            await BountyRepo.end_open_bounties_without_hunter(cfg.NO_HUNTER_TIMEOUT)

            # 找出 due_timestamp 已过期的记录
            rows = await BountyRepo.list_due_expired(now_ts())

            for bid, st in rows:
                if st == cfg.B7_SUBMIT:
                    await BountyRepo.timeout_submit_to_reopen(bid)
                elif st == cfg.B2_REVIEW:
                    await auto_accept_bounty(bot, bid)
                elif st == cfg.B3_RETURN:
                    await BountyRepo.timeout_return_to_reopen(bid)

        except Exception as e:
            logging.exception("timeout worker error: %s", e)

        await asyncio.sleep(30)


# -----------------------------
# Main
# -----------------------------

async def main():
    logging.basicConfig(level=logging.INFO)

    # 配置校验（.env 由 bounty_config.py 自动读取）
    cfg.validate()

    # init PG pool
    PGPool.DSN = cfg.DATABASE_DSN
    await PGPool.init_pool()

    # ensure schema (moved to repo)
    await BountyRepo.ensure_schema()

    bot = Bot(token=cfg.BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # timeout worker
    asyncio.create_task(bounty_timeout_worker(bot))

    logging.info("Bot started. BOARD_CHAT_ID=%s ADMIN_IDS=%s", cfg.BOARD_CHAT_ID, list(cfg.ADMIN_IDS))

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await PGPool.close()


if __name__ == "__main__":
    asyncio.run(main())
