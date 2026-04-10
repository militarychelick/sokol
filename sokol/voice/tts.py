"""
Text-to-Speech using Edge TTS
"""

from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import edge_tts

from ..core.config import VoiceConfig
from ..core.exceptions import VoiceError


@dataclass
class VoiceInfo:
    """Information about a TTS voice."""
    name: str
    short_name: str
    language: str
    gender: str
    locale: str


class TextToSpeech:
    """
    Text-to-Speech using Microsoft Edge's neural voices.
    
    Edge TTS provides high-quality neural voices for free,
    but requires internet connection.
    """
    
    def __init__(self, config: VoiceConfig) -> None:
        self.config = config
        self._voice = config.tts_voice
        self._rate = config.tts_rate
        self._communicate: edge_tts.Communicate | None = None
    
    async def initialize(self) -> None:
        """Initialize TTS system."""
        # Verify voice is available
        voices = await self.list_voices()
        voice_names = [v.short_name for v in voices]
        
        if self._voice not in voice_names:
            # Try to find a matching voice
            for v in voices:
                if v.language == self.config.stt_language:
                    self._voice = v.short_name
                    break
    
    async def speak(self, text: str) -> None:
        """
        Speak text using Edge TTS.
        
        Args:
            text: Text to speak
        """
        try:
            communicate = edge_tts.Communicate(
                text,
                self._voice,
                rate=self._rate,
            )
            
            # Stream to temporary file and play
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                temp_path = Path(f.name)
            
            await communicate.save(str(temp_path))
            
            # Play audio using Windows Media Player
            await self._play_audio(temp_path)
            
            # Cleanup
            temp_path.unlink(missing_ok=True)
            
        except Exception as e:
            raise VoiceError("Speech synthesis failed", str(e))
    
    async def speak_to_file(self, text: str, output_path: Path) -> None:
        """
        Synthesize speech to file.
        
        Args:
            text: Text to speak
            output_path: Path to save audio file
        """
        try:
            communicate = edge_tts.Communicate(
                text,
                self._voice,
                rate=self._rate,
            )
            
            await communicate.save(str(output_path))
            
        except Exception as e:
            raise VoiceError("Failed to save speech to file", str(e))
    
    async def list_voices(self, language: str | None = None) -> list[VoiceInfo]:
        """
        List available voices.
        
        Args:
            language: Filter by language code (e.g., "ru", "en")
        
        Returns:
            List of available VoiceInfo objects
        """
        try:
            voices = await edge_tts.list_voices()
            
            result = []
            for v in voices:
                voice = VoiceInfo(
                    name=v["Name"],
                    short_name=v["ShortName"],
                    language=v["Languages"][0] if v.get("Languages") else "unknown",
                    gender=v["Gender"],
                    locale=v["Locale"],
                )
                
                if language is None or language in voice.language:
                    result.append(voice)
            
            return result
            
        except Exception as e:
            raise VoiceError("Failed to list voices", str(e))
    
    def set_voice(self, voice_name: str) -> None:
        """Change the active voice."""
        self._voice = voice_name
    
    def set_rate(self, rate: str) -> None:
        """
        Set speech rate.
        
        Args:
            rate: Rate string like "+50%", "-20%", "+0%"
        """
        self._rate = rate
    
    async def _play_audio(self, file_path: Path) -> None:
        """Play audio file using Windows Media Player."""
        # Use PowerShell to play audio (works on Windows 10+)
        ps_command = f'''
        Add-Type -AssemblyName presentationCore
        $player = New-Object System.Windows.Media.MediaPlayer
        $player.Open("{file_path}")
        $player.Play()
        Start-Sleep -Milliseconds 100
        while ($player.Position -lt $player.NaturalDuration.TimeSpan -and $player.Position.TotalSeconds -gt 0) {{
            Start-Sleep -Milliseconds 100
        }}
        $player.Close()
        '''
        
        process = await asyncio.create_subprocess_exec(
            "powershell",
            "-Command",
            ps_command,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        
        await process.wait()
    
    def shutdown(self) -> None:
        """Cleanup resources."""
        pass  # No cleanup needed for Edge TTS
