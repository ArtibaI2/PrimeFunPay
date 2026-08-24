import asyncio
import os
import aiohttp
from pathlib import Path
from typing import Optional, Tuple
from utils.logger import logger

class FileUploader:
    """Handles uploading digital goods and files to various cloud hosting providers."""

    @staticmethod
    async def upload_catbox(file_bytes: bytes, filename: str) -> Optional[str]:
        """Uploads a file to Catbox.moe (permanent direct hosting)."""
        try:
            data = aiohttp.FormData()
            data.add_field('reqtype', 'fileupload')
            data.add_field('fileToUpload', file_bytes, filename=filename)
            async with aiohttp.ClientSession() as session:
                async with session.post("https://catbox.moe/user/api.php", data=data, timeout=aiohttp.ClientTimeout(total=45)) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        url = text.strip()
                        if url.startswith("http"):
                            logger.info(f"File '{filename}' successfully uploaded to Catbox: {url}")
                            return url
        except Exception as e:
            logger.error(f"Error uploading to Catbox: {e}")
        return None

    @staticmethod
    async def upload_gofile(file_bytes: bytes, filename: str) -> Optional[str]:
        """Uploads a file to Gofile.io."""
        try:
            async with aiohttp.ClientSession() as session:
                # 1. Get best server
                async with session.get("https://api.gofile.io/servers", timeout=aiohttp.ClientTimeout(total=10)) as s_resp:
                    if s_resp.status != 200:
                        return None
                    s_data = await s_resp.json()
                    servers = s_data.get("data", {}).get("servers", [])
                    if not servers:
                        return None
                    server = servers[0]["name"]

                # 2. Upload file
                data = aiohttp.FormData()
                data.add_field('file', file_bytes, filename=filename)
                async with session.post(f"https://{server}.gofile.io/contents/uploadfile", data=data, timeout=aiohttp.ClientTimeout(total=45)) as resp:
                    if resp.status == 200:
                        g_json = await resp.json()
                        page = g_json.get("data", {}).get("downloadPage")
                        if page:
                            logger.info(f"File '{filename}' successfully uploaded to Gofile: {page}")
                            return page
        except Exception as e:
            logger.error(f"Error uploading to Gofile: {e}")
        return None

    @staticmethod
    async def upload_workupload(file_bytes: bytes, filename: str) -> Optional[str]:
        """Attempts upload to Workupload, fallback to Catbox if bot-protected."""
        try:
            data = aiohttp.FormData()
            data.add_field('file', file_bytes, filename=filename)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            }
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post("https://workupload.com/api/file/upload", data=data, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status == 200:
                        res = await resp.json()
                        url = res.get("url") or res.get("data", {}).get("url")
                        if url:
                            return url
        except Exception:
            pass
        # Fallback to Catbox
        logger.info(f"Workupload direct upload redirected to cloud hosting for '{filename}'")
        return await FileUploader.upload_catbox(file_bytes, filename)

    @classmethod
    async def upload(cls, file_bytes: bytes, filename: str, service: str = "auto") -> Tuple[Optional[str], str]:
        """
        Uploads file to requested destination or auto-picks best available cloud.
        Returns (url, service_name).
        """
        service_lower = service.lower()
        if "catbox" in service_lower:
            url = await cls.upload_catbox(file_bytes, filename)
            return url, "Catbox.moe"
        elif "gofile" in service_lower:
            url = await cls.upload_gofile(file_bytes, filename)
            return url, "Gofile.io"
        elif "workupload" in service_lower:
            url = await cls.upload_workupload(file_bytes, filename)
            return url, "Workupload / Cloud"
        else:
            # Auto: try Catbox first, then Gofile
            url = await cls.upload_catbox(file_bytes, filename)
            if url:
                return url, "Catbox.moe"
            url = await cls.upload_gofile(file_bytes, filename)
            if url:
                return url, "Gofile.io"
        return None, service
