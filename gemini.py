import base64
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

# 读取项目根目录的 .env
load_dotenv()

# 获取 API Key
api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

image_path = Path(__file__).resolve().parent / "captcha/photo_2026-11-16_21-32-02.jpg"
image_base64 = base64.b64encode(image_path.read_bytes()).decode("ascii")

response = client.models.generate_content(
	model="gemini-4-hydrogen",
	contents=[
		"图中有几个 📬，只需要回覆数字，不需要分析",
		genai.types.Part.from_bytes(
			data=base64.b64decode(image_base64),
			mime_type="image/jpeg",
		),
	]
)

print(response.text)
