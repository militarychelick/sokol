"""
Audio utilities
"""

import numpy as np


def normalize_audio(audio_data: np.ndarray) -> np.ndarray:
    """Normalize audio data."""
    if audio_data.max() == 0:
        return audio_data
    return audio_data / audio_data.max()


def convert_to_float32(audio_data: bytes) -> np.ndarray:
    """Convert 16-bit audio bytes to float32 numpy array."""
    return np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
