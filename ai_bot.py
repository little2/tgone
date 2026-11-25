"""力荐凯哥机器人交互流程。"""

from __future__ import annotations

import asyncio
import re
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from human_bot_operator import HumanBotOperator


class AIBot:
	@staticmethod
	def _calculate_verification_answer(text: str) -> str:
		"""找出最后一个四则运算验证题并返回答案按钮文字。"""
		if not isinstance(text, str):
			raise TypeError("验证题内容必须是字符串")

		text = text.replace("−", "-")
		matches = re.findall(
			r"(-?\d+(?:\.\d+)?)\s*([+\-*/×÷xX])\s*(-?\d+(?:\.\d+)?)\s*=\s*\?",
			text,
		)
		if not matches:
			raise ValueError("找不到格式为『数字 运算符 数字 = ?』的验证题")

		left_text, operator, right_text = matches[-1]
		left = Decimal(left_text)
		right = Decimal(right_text)

		if operator == "+":
			answer = left + right
		elif operator == "-":
			answer = left - right
		elif operator in {"*", "×", "x", "X"}:
			answer = left * right
		else:
			if right == 0:
				raise ValueError("验证题不能除以零")
			answer = left / right

		answer_text = format(answer, "f")
		if "." in answer_text:
			answer_text = answer_text.rstrip("0").rstrip(".")
		return "0" if answer == 0 else answer_text

	@staticmethod
	async def juno_fnj7ubot(op: HumanBotOperator) -> None:
		# oixel.net
		target_bot = await op._resolve_input_entity("@juno_fnj7ubot")
		start_result = await op.capture_bot_messages(target_bot, "/start OnQfPZu8")
		if start_result:
			check_result = await op.capture_bot_messages(target_bot, "📅 每日签到")
			if check_result:
				board_id = check_result[-1].id
				checking = await op.capture_bot_messages(
					target_bot, click_button_title="💎", message_id=board_id
				)
				# print(f"checking={checking}", flush=True)
		else:
			print("未收到任何消息", flush=True)

	@staticmethod
	async def cyaibox118bot(op: HumanBotOperator) -> None:
		# oixel.net
		target_bot = await op._resolve_input_entity("@cyaibox118bot")
		await op.join_chat("https://t.me/addlist/hv_WjtuvpvcyMmNl")
		await op.join_chat("https://t.me/cyberso77")


		start_result = await op.capture_bot_messages("@cyberso77", "赛博短片")
		

		start_result = await op.capture_bot_messages(target_bot, "/start i7154552172")
		if start_result:
			check_result = await op.capture_bot_messages(target_bot, "签到")
			
		else:
			print("未收到任何消息", flush=True)     

	@staticmethod
	async def QQCC_123_bot(op: HumanBotOperator) -> None:
		# #https://t.me/AiVisionAV
		target_bot = await op._resolve_input_entity("@QQCC_123_bot")
		await op.join_chat("https://t.me/+-QVG_AV94eViYzRl")
		await op.join_chat("https://t.me/AiVisionAV")

		start_result = await op.capture_bot_messages(target_bot, "/start 7154552172")
		if start_result:
			check_result = await op.capture_bot_messages(target_bot, "📅 每日签到")
			
		else:
			print("未收到任何消息", flush=True)   

	@staticmethod
	async def huyaback_bot(op: HumanBotOperator) -> None:
		# 糖心-官方脱衣定制
		target_bot = await op._resolve_input_entity("@huyaback_bot")
		# await op.join_chat("https://t.me/+-QVG_AV94eViYzRl")
		# await op.join_chat("https://t.me/Huyafd_bot")
		start_result = await op.capture_bot_messages("@Huyafd_bot", "/start")
		start_result = await op.capture_bot_messages(target_bot, "/start UKL2LEHX24J7")
		if start_result:
			check_result = await op.capture_bot_messages(target_bot, "每日签到")
			
		else:
			print("未收到任何消息", flush=True)              

	@staticmethod
	async def linglongai_10bot(op: HumanBotOperator) -> None:
		# 玲珑Ai10号
		target_bot = await op._resolve_input_entity("@linglongai_10bot")
		await op.join_chat("https://t.me/linglongai5")
		# await op.join_chat("https://t.me/Huyafd_bot")
	   
		start_result = await op.capture_bot_messages(target_bot, "/start share_7154552172")
		if start_result:
			check_result = await op.capture_bot_messages(target_bot, "📅 签到")
			
		else:
			print("未收到任何消息", flush=True)    

	@staticmethod
	async def gaoren1231211_bot(op: HumanBotOperator) -> None:
		# #http://gaoren.me/
		target_bot = await op._resolve_input_entity("@gaoren1231211_bot")
		# await op.join_chat("https://t.me/linglongai5")
		# await op.join_chat("https://t.me/Huyafd_bot")
		newbio = '''便宜好用的全能视频特效 bot
点击即可体验
https://gaoren.me?start=ref_6941890966'''
		await op.update_bio(newbio)
		await asyncio.sleep(15)

		start_result = await op.capture_bot_messages(target_bot, "/start ref_7154552172")
		if start_result:
			for attempt in range(1, 4):
				check_result = await op.capture_bot_messages(target_bot, "📅 签到")
				if any(
					keyword in (
						getattr(message, "text", None)
						or getattr(message, "message", None)
						or ""
					)
					for message in (check_result or [])
					for keyword in ("签到成功", "今天已签到")
				):
					print("已确认签到成功或今天已签到", flush=True)
					break
				if attempt < 3:
					print(f"第 {attempt} 次未确认签到成功，10 秒后重试", flush=True)
					await asyncio.sleep(10)
			else:
				print("已尝试签到 3 次，仍未收到签到成功", flush=True)
		else:
			print("未收到任何消息", flush=True)


		await op.update_bio("")
		

	@staticmethod
	async def ShuoWen_bot(op: HumanBotOperator) -> None:
		# 玲珑Ai10号
		target_bot = await op._resolve_input_entity("@ShuoWen_bot")
		# await op.join_chat("https://t.me/linglongai5")
		# await op.join_chat("https://t.me/Huyafd_bot")
	   


		backup_result = await op.capture_bot_messages("@tiankelong5bot", "/start VNB6Z1SRHHK172KA")

		start_result = await op.capture_bot_messages(target_bot, "/start VNB6Z1SRHHK172KA")
		if start_result:
			check_result = await op.capture_bot_messages(target_bot, "🌍 每日签到")
			if check_result:
				board_id = check_result[-1].id
				checking = await op.capture_bot_messages(
					target_bot, click_button_title="发送编号", message_id=board_id
				)
		else:
			print("未收到任何消息", flush=True)   

	@staticmethod
	async def ftcyy04bot(op: HumanBotOperator) -> None:
		# 玲珑Ai10号
		target_bot = await op._resolve_input_entity("@ftcyy04bot")
		await op.join_chat("https://t.me/+B08LK_uykbI0ZGUx")
		# await op.join_chat("https://t.me/Huyafd_bot")
	   
		start_result = await op.capture_bot_messages(target_bot, "/start C32378EE")
		if start_result:
			# check_result = await op.capture_bot_messages(target_bot, "📅 签到")
		   
			board_id = start_result[-1].id
			checking = await op.capture_bot_messages(
				target_bot, click_button_title="积分", message_id=board_id
			)

			if checking:
				# board_id = start_result[-1].id
				checking2 = await op.capture_bot_messages(
					target_bot, click_button_title="签到", message_id=board_id
				)

			# print(f"checking={checking2}", flush=True)
		else:
			print("未收到任何消息", flush=True)
			
	@staticmethod
	async def xhgsgk_bot(op: HumanBotOperator) -> None:
		# 一诺
		target_bot = await op._resolve_input_entity("@xhgsgk_bot")
		await op.join_chat("https://t.me/addlist/CfQmexieO-84ZmU1")
		# await op.join_chat("https://t.me/Huyafd_bot")
	   
		start_result = await op.capture_bot_messages(target_bot, "/start yoQyA2fgRxrxkgR")
		
		if start_result:
			# check_result = await op.capture_bot_messages(target_bot, "📅 签到")
			# print(f"start_result={start_result[-1]}", flush=True)
			if "完成注册" in start_result[-1].text:
				board_id = start_result[-1].id
				registration_completed = False

				for i in range(1, 17):
					checking = await op.capture_bot_messages(
						target_bot, click_button_title=str(i), message_id=board_id
					)
				  
					await asyncio.sleep(3)
					if not checking:
						print(f"点 {i} 后未收到机器人回覆，继续尝试。", flush=True)
						continue

					checking_message = checking[-1]
					checking_text = (
						getattr(checking_message, "message", None)
						or getattr(checking_message, "text", None)
						or ""
					)
					if "答案错误" in checking_text:
						print(f"点 {i} 错误，重新开始注册", flush=True)
						start_result = await op.capture_bot_messages(target_bot, "/start")
						if not start_result:
							print("重新开始注册后未收到机器人回覆。", flush=True)
							break
						board_id = start_result[-1].id
						continue

					# 🎉 验证成功！注册完成！欢迎使用！
					print(f"22=>{checking_text}", flush=True)
					registration_completed = True
					break

				if registration_completed:
					print("完成注册", flush=True)
				else:
					print("未能确认注册完成", flush=True)
		else:
			print("未收到任何消息", flush=True)  

		qd_result = await op.capture_bot_messages(target_bot, "/qd")
		if not qd_result:
			print("未收到签到验证题", flush=True)
			return

		verification_message = qd_result[-1]
		verification_text = (
			getattr(verification_message, "text", None)
			or getattr(verification_message, "message", None)
			or ""
		)
		answer = AIBot._calculate_verification_answer(verification_text)
		print(f"签到验证答案：{answer}", flush=True)
		await op.capture_bot_messages(
			target_bot,
			click_button_title=answer,
			message_id=verification_message.id,
		)

	@staticmethod
	async def dkeiwfBot(op: HumanBotOperator) -> None:
		# 窝趣免费AI脱衣换脸俱乐部
		target_bot = await op._resolve_input_entity("@dkeiwfBot")
		# await op.join_chat("https://t.me/linglongai5")
		# await op.join_chat("https://t.me/Huyafd_bot")
	   
		start_result = await op.capture_bot_messages(target_bot, "/start 06043D92-C56B-EB1F-C241-6344B6EA82F6")
		if start_result:
			board_id = start_result[-1].id
			agree = await op.capture_bot_messages(
				target_bot, click_button_title="同意", message_id=board_id
			)

			if agree:
				board_id = agree[-1].id
				checkin = await op.capture_bot_messages(
					target_bot, click_button_title="签到", message_id=board_id
				)

	@staticmethod
	async def huangdoubaozi_bot(op: HumanBotOperator) -> None:
		# https://aimu.art/?ref=6941890966
		target_bot = await op._resolve_input_entity("@huangdoubaozi_bot")
		# await op.join_chat("https://t.me/linglongai5")
		await op.join_chat("https://t.me/aitutu55")
	   
		me = await op.client.get_me()
	
		newbio = f'''https://aimu.art/?ref={int(me.id)}
一键AI脱衣，注册送💎白嫖！'''
		await op.update_bio(newbio)
		await asyncio.sleep(15)
		start_result = await op.capture_bot_messages(target_bot, "/start p_7154552172")
		

		if start_result:
			for attempt in range(1, 4):
				check_result = await op.capture_bot_messages(target_bot, "📅 签到")
				if any(
					keyword in (
						getattr(message, "text", None)
						or getattr(message, "message", None)
						or ""
					)
					for message in (check_result or [])
					for keyword in ("签到成功", "已签到")
				):
					print("已确认签到成功或今天已签到", flush=True)
					break
				if attempt < 3:
					print(f"第 {attempt} 次未确认签到成功，10 秒后重试", flush=True)
					await asyncio.sleep(10)
			else:
				print("已尝试签到 3 次，仍未收到签到成功", flush=True)
		else:
			print("未收到任何消息", flush=True)


		await op.update_bio("")



	@staticmethod
	async def LiteAI_ai(op: HumanBotOperator) -> None:
		# 小艾
		target_bot = await op._resolve_input_entity("@LiteAI_ai")
		# await op.join_chat("https://t.me/linglongai5")
		# await op.join_chat("https://t.me/Huyafd_bot")
   
	

		start_result = await op.capture_bot_messages(target_bot, "/start Yt9TUIUS")
		if start_result:
			qd_result = await op.capture_bot_messages(target_bot, "⭐ 今日签到")
			if not qd_result:
				print("未收到签到验证题", flush=True)
				return

			verification_message = qd_result[-1]
			verification_text = (
				getattr(verification_message, "text", None)
				or getattr(verification_message, "message", None)
				or ""
			)
			answer = AIBot._calculate_verification_answer(verification_text)
			print(f"签到验证答案：{answer}", flush=True)
			await op.capture_bot_messages(
				target_bot,
				click_button_title=answer,
				message_id=verification_message.id,
			)

			
		else:
			print("未收到任何消息", flush=True)    
		await op.update_bio("")

	@staticmethod
	async def myai_01_bot(op: HumanBotOperator) -> None:
		# https://t.me/myai_1q2w3e4r
		await op.join_chat("https://t.me/myai_home")
		target_bot = await op._resolve_input_entity("@myai_01_bot")
		start_result = await op.capture_bot_messages(target_bot, "/start CFC50F06_cn")
		if start_result:
			check_result = await op.capture_bot_messages(target_bot, "📅 每日签到")
			if check_result:
				board_id = check_result[-1].id
				checking = await op.capture_bot_messages(
					target_bot, click_button_title="💎", message_id=board_id
				)
				# print(f"checking={checking}", flush=True)
		else:
			print("未收到任何消息", flush=True)