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

    async def analyze_image(
        self,
        image_url: str,
        prompt: str = "Describe this image in detail. Extract any measurements, product names, or technical specifications visible."
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze an image using GPT-4 Vision.

        Args:
            image_url: URL of the image to analyze
            prompt: Prompt for the vision model

        Returns:
            Dictionary with analysis results or None if failed
        """
        if not self._api_key:
            logger.warning("OpenAI API key not configured — skipping image analysis")
            return None

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self._api_url,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o",
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": image_url}
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
                    logger.info("vision_analysis_success  image_url=%s", image_url[:100])
                    return {"description": content, "raw_response": data}
                else:
                    logger.error(
                        "vision_analysis_failed  status=%d  error=%s",
                        response.status_code, response.text[:200]
                    )
                    return None

        except Exception as e:
            logger.exception("vision_analysis_exception  error=%s", str(e))
            return None

    async def extract_measurements(
        self,
        image_url: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Extract measurements from an image for quote purposes.

        Args:
            image_url: URL of the image to analyze

        Returns:
            Dictionary with extracted measurements or None if failed
        """
        prompt = (
            "Analyze this image and extract any measurements visible. "
            "Look for dimensions like width, height, length, area in meters or centimeters. "
            "Also identify the type of surface or product (e.g., window, glass, mirror, etc.). "
            "Return the information in a structured format."
        )

        result = await self.analyze_image(image_url, prompt)
        if result:
            return {
                "description": result["description"],
                "source": "vision_analysis"
            }
        return None


# Global instance
vision_service = VisionService()
