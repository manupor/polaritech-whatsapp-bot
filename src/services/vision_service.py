"""
Vision service for processing images using OpenAI GPT-4 Vision.
Extracts information from images like measurements, product types, etc.
"""

import logging
import base64
from typing import Optional, Dict, Any

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)


class VisionService:
    """Service for processing images with OpenAI Vision API."""

    def __init__(self, api_key: str = ""):
        self._api_key = api_key or settings.openai_api_key
        self._api_url = "https://api.openai.com/v1/chat/completions"

    async def _download_image(self, image_url: str, access_token: str) -> Optional[bytes]:
        """
        Download image from WhatsApp Media URL.

        Args:
            image_url: Temporary WhatsApp media URL
            access_token: WhatsApp access token for authentication

        Returns:
            Image bytes or None if failed
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    image_url,
                    headers={"Authorization": f"OAuth {access_token}"}
                )

                if response.status_code == 200:
                    logger.info("image_download_success  size=%d bytes", len(response.content))
                    return response.content
                else:
                    logger.error(
                        "image_download_failed  status=%d  error=%s",
                        response.status_code, response.text[:200]
                    )
                    return None

        except Exception as e:
            logger.exception("image_download_exception  error=%s", str(e))
            return None

    async def analyze_image(
        self,
        image_url: str,
        access_token: str = "",
        prompt: str = "Describe this image in detail. Extract any measurements, product names, or technical specifications visible."
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze an image using GPT-4 Vision.

        Args:
            image_url: URL of the image to analyze
            access_token: WhatsApp access token to download the image
            prompt: Prompt for the vision model

        Returns:
            Dictionary with analysis results or None if failed
        """
        if not self._api_key:
            logger.warning("OpenAI API key not configured — skipping image analysis")
            return None

        whatsapp_token = access_token or settings.whatsapp_access_token
        if not whatsapp_token:
            logger.warning("WhatsApp access token not configured — cannot download image")
            return None

        # Download image bytes from WhatsApp
        image_bytes = await self._download_image(image_url, whatsapp_token)
        if not image_bytes:
            return None

        # Convert to base64
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{base64_image}"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self._api_url,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": data_url}
                                    }
                                ]
                            }
                        ],
                        "max_tokens": 500,
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    logger.info("vision_analysis_success  description=%s", content[:100])
                    return {"description": content, "raw_response": data}
                else:
                    logger.error(
                        "vision_analysis_failed  status=%d  error=%s",
                        response.status_code, response.text[:500]
                    )
                    return None

        except Exception as e:
            logger.exception("vision_analysis_exception  error=%s", str(e))
            return None

    async def extract_measurements(
        self,
        image_url: str,
        access_token: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Extract measurements from an image for quote purposes.

        Args:
            image_url: URL of the image to analyze
            access_token: WhatsApp access token to download the image

        Returns:
            Dictionary with extracted measurements or None if failed
        """
        prompt = (
            "Analyze this image and extract any measurements visible. "
            "Look for dimensions like width, height, length, area in meters or centimeters. "
            "Also identify the type of surface or product (e.g., window, glass, mirror, etc.). "
            "Return the information in a structured format."
        )

        result = await self.analyze_image(image_url, access_token, prompt)
        if result:
            return {
                "description": result["description"],
                "source": "vision_analysis"
            }
        return None


# Global instance
vision_service = VisionService()
