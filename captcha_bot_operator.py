"""独立的验证码处理逻辑：另一个 Telegram Bot 负责展示和回调选项。"""

import asyncio
import io
import json
import os
import uuid
from typing import Any

from aiogram import Bot
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup



class CaptchaBotOperator:
    """负责处理验证码图片、转发给真人用户，并接收用户选择结果。"""

    PROTECTED_MEDIA_TRANSFER_TIMEOUT_SECONDS = 5 * 60
    CAPTCHA_SELECTION_TIMEOUT_SECONDS = 30
    _captcha_selection_waiters: dict[str, asyncio.Future[str]] = {}
    _captcha_bridge: dict[str, dict[str, Any]] = {}
    _bot_cache: dict[str, Bot] = {}
    captcha_bot_name : str = ""
    zttower_bot_name : str = ""
    reward_bot_name: str = ""

    def __init__(self, client: Any) -> None:
        self.client = client

    @staticmethod
    async def _get_bot(token: str) -> Bot:
        """复用单例 Bot 实例，避免每次处理验证码都重新初始化。"""
        token = (token or "").strip()
        if not token:
            raise ValueError("BOT_TOKEN 不可为空")
        bot = CaptchaBotOperator._bot_cache.get(token)
        if bot is None:
            bot = Bot(token=token)
            CaptchaBotOperator._bot_cache[token] = bot
            me = await bot.get_me()
            CaptchaBotOperator.captcha_bot_name = me.username

        return bot




    @staticmethod
    async def _answer_group_callback_query(
        callback_query_id: str | None,
        text: str,
        *,
        show_alert: bool = False,
    ) -> None:
        """通过 bot token 回覆群组中的 callback query，通知最终结果。"""
        if not callback_query_id:
            return
        bot_token = (os.getenv("FREE_BOT_TOKEN") or "").strip()
        if not bot_token:
            return
        bot = await CaptchaBotOperator._get_bot(bot_token)
        try:
            await bot.answer_callback_query(
                callback_query_id=callback_query_id,
                text=text,
                show_alert=show_alert,
            )
        except Exception as exc:
            print(f"⚠️ 回应验证码群组回调失败：{exc}", flush=True)

    async def handle_captcha(self, response: Any, user_id: int | None = None, reward_bot_name: str | None = None) -> None:
        """处理验证码响应，并将验证码桥接到指定群组回调。"""
        if user_id is None:
            print(f"⚠️ 未指定 user_id，无法转发验证码图片到指定用户。", flush=True)
            user_id = -1004380843996
        user_id = int(user_id)

        if reward_bot_name:
            CaptchaBotOperator.reward_bot_name = str(reward_bot_name).strip().removeprefix("@")
        elif not CaptchaBotOperator.reward_bot_name:
            CaptchaBotOperator.reward_bot_name = str(
                os.getenv("REWARD_BOT_NAME", "")
            ).strip().removeprefix("@")
        

        free_bot_token = (os.getenv("FREE_BOT_TOKEN") or "").strip()
        if not free_bot_token:
            print("⚠️ 未配置 FREE_BOT_TOKEN，无法转发验证码图片到指定用户。", flush=True)
            return

        bot = await self._get_bot(free_bot_token)
        notify_message = None
        media_buffer = io.BytesIO()
        try:
            announcement = (
                "✈️【飞行红包随机抢答活动广播】\n\n"
                "各位旅客请注意，各位旅客请注意！\n\n"
                "飞行红包随机抢答活动即将开始，请各位旅客做好准备，及时关注广播与题目。\n\n"
                "本次活动将进行限时抢答：\n"
                "🎫 成功答对问题的旅客，可获得 6 小时飞行时长；\n"
                "⚠️ 抢答失败的旅客，将扣除 1 小时时长。\n\n"
                "请各位旅客确认自己的脑容量、反应速度及求生欲均处于正常状态。\n\n"
                "倒计时即将开始——\n"
                "祝各位旅客抢答顺利，飞行愉快！✈️"
            )

            notice_task = asyncio.create_task(
                bot.send_message(
                    chat_id=user_id,
                    text=announcement,
                )
            )
            download_task = asyncio.create_task(
                self.client.download_media(response, file=media_buffer)
            )
            notice_result, downloaded = await asyncio.gather(
                notice_task,
                asyncio.wait_for(
                    download_task,
                    timeout=self.PROTECTED_MEDIA_TRANSFER_TIMEOUT_SECONDS,
                ),
            )
            notify_message = notice_result
        except asyncio.TimeoutError:
            print(
                f"❗️ 验证码图片下载超时，user_id={user_id}，message_id={getattr(response, 'id', 'unknown')}",
                flush=True,
            )
            return
        except Exception as exc:
            print(
                f"❗️ 发送验证码预告或下载失败，user_id={user_id}：{exc}",
                flush=True,
            )
            return

        if notify_message is not None:
            async def _delete_notice() -> None:
                try:
                    await asyncio.sleep(25)
                    await bot.delete_message(
                        chat_id=user_id,
                        message_id=notify_message.message_id,
                    )
                except Exception as exc:
                    print(f"⚠️ 删除验证码预告消息失败：{exc}", flush=True)

            asyncio.create_task(_delete_notice())

        if downloaded is None or media_buffer.tell() == 0:
            print(f"❗️ 验证码图片为空，未转发给 user_id={user_id}", flush=True)
            return

        file_name = getattr(getattr(response, "file", None), "name", None)
        if not file_name:
            extension = getattr(getattr(response, "file", None), "ext", None) or ".jpg"
            file_name = f"captcha_{getattr(response, 'id', 'captcha')}{extension}"
        media_buffer.name = file_name
        media_buffer.seek(0)
        media_file = BufferedInputFile(media_buffer.getvalue(), filename=file_name)

        caption = str(getattr(response, "raw_text", "") or "").strip() or None
        if caption:
            if "只数清晰的大图案" in caption:
                caption = (
                    "只数明显的大图案，小而淡的背景图案不要算。\n"
                    "找出出现次数最多的图案，并选择它的数量。\n"
                    "如果有多个图案数量相同，选择这个数量即可。"
                )
            elif "请选择与上方物体相同。" in caption:
                caption = (
                    "请选择与上方物体相同的图案，\n"
                    "图案可能只是旋转了不同角度。"
                )
            else:
                print(f"验证码图片 caption: {caption}", flush=True)

        selection_future = None
        task_id = None
        sent_message = None
        bridge: dict[str, Any] | None = None

        def is_transient_bot_error(exc: Exception) -> bool:
            message_text = str(exc)
            return (
                "ClientConnectorError" in message_text
                or "Cannot connect to host" in message_text
                or "Connection reset" in message_text
                or "Connection closed" in message_text
                or "Server closed the connection" in message_text
                or "ConnectionError" in type(exc).__name__
            )

        async def click_origin_captcha(selected_value: str) -> Any:
            """点击原始验证码按钮；若原消息对象失效则刷新后重试一次。"""
            button_matcher = (
                lambda button_text: str(button_text or "").strip() == str(selected_value)
            )
            try:
                return await response.click(text=button_matcher)
            except Exception as exc:
                error_text = str(exc).lower()
                # 原消息对象偶尔会失效，刷新消息后再尝试一次。
                if (
                    "message id is invalid" not in error_text
                    and "can't do that operation on such message" not in error_text
                ):
                    raise

                origin_chat_id = getattr(response, "chat_id", None)
                origin_message_id = getattr(response, "id", None)
                if origin_chat_id is None or origin_message_id is None:
                    raise

                refreshed = await self.client.get_messages(origin_chat_id, ids=origin_message_id)
                if refreshed is None:
                    raise

                return await refreshed.click(text=button_matcher)

        try:
            for attempt in range(1, 4):
                try:
                    if getattr(response, "photo", None) is not None:
                        task_id = uuid.uuid4().hex
                        selection_future = asyncio.get_running_loop().create_future()
                        self._captcha_selection_waiters[task_id] = selection_future
                        bridge = {
                            "task_id": task_id,
                            "origin_chat_id": getattr(response, "chat_id", None),
                            "origin_message_id": getattr(response, "id", None),
                            "group_chat_id": user_id,
                            "from_user_id": None,
                            "callback_query_id": None,
                            "selected": None,
                            "confirmed": False,
                        }
                        self._captcha_bridge[task_id] = bridge

                        keyboard = [
                            [
                                InlineKeyboardButton(text="1", callback_data=f"ca:{task_id}:1"),
                                InlineKeyboardButton(text="2", callback_data=f"ca:{task_id}:2"),
                                InlineKeyboardButton(text="3", callback_data=f"ca:{task_id}:3"),
                                InlineKeyboardButton(text="4", callback_data=f"ca:{task_id}:4"),
                            ],
                            [
                                InlineKeyboardButton(text="5", callback_data=f"ca:{task_id}:5"),
                                InlineKeyboardButton(text="6", callback_data=f"ca:{task_id}:6"),
                                InlineKeyboardButton(text="7", callback_data=f"ca:{task_id}:7"),
                                InlineKeyboardButton(text="8", callback_data=f"ca:{task_id}:8"),
                            ],
                        ]

                        sent_message = await bot.send_photo(
                            chat_id=user_id,
                            photo=media_file,
                            caption=caption,
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
                        )
                    elif getattr(response, "document", None) is not None:
                        sent_message = await bot.send_document(
                            chat_id=user_id,
                            document=media_file,
                            caption=caption,
                        )
                    else:
                        sent_message = await bot.send_document(
                            chat_id=user_id,
                            document=media_file,
                            caption=caption,
                        )

                    print(f"✅ 已将验证码图片转发给用户 {user_id}", flush=True)
                    break
                except Exception as exc:
                    if attempt < 3 and is_transient_bot_error(exc):
                        delay = 2 ** (attempt - 1)
                        print(
                            f"⚠️ 发送验证码到 user_id={user_id} 时遇到临时连接错误，重试 {attempt + 1}/3（{delay}s）：{exc}",
                            flush=True,
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise

            if selection_future is not None and sent_message is not None:
                try:
                    selected = await asyncio.wait_for(
                        selection_future,
                        timeout=self.CAPTCHA_SELECTION_TIMEOUT_SECONDS,
                    )

                    if bridge is not None:
                        bridge["selected"] = selected
                    clicked_user_id = bridge.get("from_user_id") if bridge is not None else None

                    try:
                        click_result = await click_origin_captcha(selected)
                        '''
                        click_result=BotCallbackAnswer(cache_time=0, alert=False, has_url=False, native_ui=True, message='验证错误，还可尝试 1 次。', url=None) clicked_user_id=8696673867
                        click_result=BotCallbackAnswer(cache_time=0, alert=True, has_url=False, native_ui=True, message='验证失败次数过多，请稍后重试。', url=None) clicked_user_id=8696673867

                        '''


                        print(
                            f"click_result={click_result} clicked_user_id={clicked_user_id}",
                            flush=True,
                        )
                        if click_result and getattr(click_result, "message", None) == "验证成功。":



                            if bridge is not None and bridge.get("callback_query_id"):
                                await self._answer_group_callback_query(
                                    bridge["callback_query_id"],
                                    "你已抢答成功",
                                    show_alert=True,
                                )
                            bridge["confirmed"] = True

                            try:
                                json_data = {}
                                json_data["action"] = "captcha"
                                json_data["user_id"] = clicked_user_id
                                json_data["minutes"] = 60*(6)
                                json_text = json.dumps(json_data, ensure_ascii=False)
                                award_chat_id = (
                                    f"@{CaptchaBotOperator.reward_bot_name}"
                                    if CaptchaBotOperator.reward_bot_name
                                    else str(user_id)
                                )
                                await bot.send_message(
                                    chat_id=award_chat_id,
                                    text=f"{json_text}",
                                )
                                

                                print(
                                    f"✅ 验证码验证成功：user_id={user_id} task_id={task_id} "
                                    f"clicked_user_id={clicked_user_id}",
                                    flush=True,
                                )

                            except Exception as exc:
                                print(
                                    f"[CAPTCHA_SELECTION] failed to notify: {exc}",
                                    flush=True,
                                )


                       
                        elif click_result and getattr(click_result, "message") is not None:
                            if bridge is not None and bridge.get("callback_query_id"):
                                await self._answer_group_callback_query(
                                    bridge["callback_query_id"],
                                    "你回答错误",
                                    show_alert=True,
                                )

                            try:
                                json_data = {}
                                json_data["action"] = "captcha"
                                json_data["user_id"] = clicked_user_id
                                json_data["minutes"] = 60*(-1)
                                json_text = json.dumps(json_data, ensure_ascii=False)
                                award_chat_id = (
                                    f"@{CaptchaBotOperator.reward_bot_name}"
                                    if CaptchaBotOperator.reward_bot_name
                                    else str(user_id)
                                )
                                await bot.send_message(
                                    chat_id=award_chat_id,
                                    text=f"{json_text}",
                                )

                                print(
                                    f"❌ 验证码验证失败：user_id={user_id} task_id={task_id} "
                                    f"clicked_user_id={clicked_user_id} message={getattr(click_result, 'message', None)}",
                                    flush=True,
                                )

                            except Exception as exc:
                                print(
                                    f"[CAPTCHA_SELECTION] failed to notify: {exc}",
                                    flush=True,
                                )

                         
                        else:
                            print(
                                f"❌ 验证码验证失败：user_id={user_id} task_id={task_id} "
                                f"clicked_user_id={clicked_user_id}",
                                flush=True,
                            )
                            if bridge is not None and bridge.get("callback_query_id"):
                                await self._answer_group_callback_query(
                                    bridge["callback_query_id"],
                                    "你回答错误或未抢答成功",
                                    show_alert=True,
                                )
                    except Exception as exc:
                        print(
                            f"❌ 点击验证码原始按钮失败：selected={selected} "
                            f"clicked_user_id={clicked_user_id} error={exc}",
                            flush=True,
                        )
                        if bridge is not None and bridge.get("callback_query_id"):
                            await self._answer_group_callback_query(
                                bridge["callback_query_id"],
                                "抢答失败",
                                show_alert=True,
                            )
                except asyncio.TimeoutError:
                    print(
                        f"等待验证码按钮选择超时：user_id={user_id} task_id={task_id}",
                        flush=True,
                    )
                    

                if task_id is not None:
                    waiter = self._captcha_selection_waiters.get(task_id)
                    if waiter is selection_future:
                        self._captcha_selection_waiters.pop(task_id, None)
                    self._captcha_bridge.pop(task_id, None)
                try:
                    if sent_message is not None:
                        await bot.delete_message(chat_id=user_id, message_id=sent_message.message_id)
                except Exception as exc:
                    if "not found" not in str(exc).lower() and "message to delete" not in str(exc).lower():
                        pass
        except Exception as exc:
            print(f"❗️ 发送验证码到 user_id={user_id} 失败：{exc}", flush=True)
        finally:
            if task_id is not None:
                waiter = self._captcha_selection_waiters.get(task_id)
                if waiter is selection_future:
                    self._captcha_selection_waiters.pop(task_id, None)
                self._captcha_bridge.pop(task_id, None)

    @classmethod
    async def handle_captcha_callback(cls, callback_query: Any) -> bool:
        """处理验证码按钮选择，并唤醒等待中的 handle_captcha。"""
        data = str(getattr(callback_query, "data", "") or "")
        if not data.startswith("ca:"):
            return False

        parts = data.split(":", 2)
        if len(parts) != 3:
            print(f"收到无效验证码按钮资料：data={data}", flush=True)
            return True

        _, task_id, selected = parts
        from_user = getattr(callback_query, "from_user", None)
        message = getattr(callback_query, "message", None)
        user_id = getattr(from_user, "id", None)
        message_id = getattr(message, "message_id", None)

        bridge = cls._captcha_bridge.get(task_id)
        if bridge is not None:
            bridge["callback_query_id"] = getattr(callback_query, "id", None)
            bridge["selected"] = selected
            bridge["group_chat_id"] = getattr(message, "chat_id", None) or bridge.get("group_chat_id")
            bridge["from_user_id"] = user_id or bridge.get("user_id")

        waiter = cls._captcha_selection_waiters.get(task_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(selected)

        cls._captcha_selection_waiters.pop(task_id, None)
        try:
            await message.delete()
        except Exception:
            pass
        return True


__all__ = ["CaptchaBotOperator"]
