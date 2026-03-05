import os
import re
import base64
import uuid
from typing import Optional
from pydantic import BaseModel, Field
import httpx
from app.tools.base import BaseTool
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
IMAGE_MODEL = "google/gemini-3.1-flash-image-preview"


class GenerateImageArgs(BaseModel):
    prompt: str = Field(description="A detailed description of the image to generate.")
    filename: str = Field(
        description="Optional output filename (e.g. 'dog.png'). Defaults to a generated name.",
        default=None,
    )


class GenerateImageTool(BaseTool):
    name = "generate_image"
    description = (
        "Generate an image from a text prompt using Gemini Flash. "
        "The image will be attached to your response as a native file upload. "
        "Provide a vivid, detailed prompt for best results."
    )
    args_schema = GenerateImageArgs

    async def run(self, args: GenerateImageArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        if not OPENROUTER_API_KEY:
            return "Error: OPENROUTER_API_KEY is not set."

        try:
            # Use raw HTTP because OpenRouter returns images in a `message.images`
            # field that the OpenAI SDK does not expose.
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": IMAGE_MODEL,
                        "modalities": ["text", "image"],
                        "messages": [
                            {"role": "user", "content": args.prompt}
                        ],
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            message = data["choices"][0]["message"]

            # Images come back in message.images[] as data URLs
            images = message.get("images", [])
            # Fallback: also check message.content for inline data URLs
            content = message.get("content") or ""

            data_url = None
            if images:
                data_url = images[0].get("image_url", {}).get("url", "")
            elif "data:image" in content:
                match = re.search(r"(data:image/[\w+]+;base64,[A-Za-z0-9+/=\s]+)", content)
                if match:
                    data_url = match.group(1)

            if not data_url or "base64," not in data_url:
                return f"Error: The model did not return an image. Response content: {content[:500]}"

            # Parse the data URL
            header, b64_data = data_url.split("base64,", 1)
            img_format_match = re.search(r"image/([\w+]+)", header)
            img_format = img_format_match.group(1) if img_format_match else "png"

            img_data = base64.b64decode(b64_data)

            # Determine filename and extension
            ext = img_format.replace("+", "")
            filename = args.filename or f"generated_{uuid.uuid4().hex[:8]}.{ext}"
            if not os.path.splitext(filename)[1]:
                filename = f"{filename}.{ext}"

            file_path = os.path.join("/tmp", filename)
            with open(file_path, "wb") as f:
                f.write(img_data)

            return f"__ATTACHMENT__|||{file_path}|||{filename}"

        except Exception as e:
            return f"Error generating image: {str(e)}"
