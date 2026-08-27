import os
import math
import struct
import wave
import logging
from branding_generator.utils import ensure_dir

logger = logging.getLogger("pyflare-brand")

def write_wave_file(path, freqs, duration=0.8, rate=44100):
    ensure_dir(os.path.dirname(path))
    with wave.open(path, 'w') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        num_samples = int(duration * rate)
        for i in range(num_samples):
            t = float(i) / rate
            val = 0
            for idx, freq in enumerate(freqs):
                # Arpeggiate by delaying the start of each frequency
                delay = idx * 0.08
                if t >= delay:
                    t_note = t - delay
                    envelope = math.exp(-6 * t_note / (duration - delay)) * (1.0 - math.exp(-30 * t_note / duration))
                    val += math.sin(2 * math.pi * freq * t_note) * envelope
            val = val / len(freqs)
            sample = int(val * 32767 * 0.4)
            wav.writeframesraw(struct.pack('<h', sample))


def generate_all_sounds(target_root):
    sounds_dir = os.path.join(target_root, "sounds")
    ensure_dir(sounds_dir)
    
    sounds_config = {
        "startup": [440, 554, 659, 880], # A major chord
        "shutdown": [880, 659, 554, 440], # Descending
        "notification": [523, 659],
        "success": [523, 659, 784, 1046],
        "error": [220, 233], # low dissonance
        "warning": [440, 466],
        "login": [349, 440, 523, 698],
        "logout": [698, 523, 440, 349],
        "recycle": [300, 150],
        "empty_trash": [200, 100]
    }
    
    for filename, freqs in sounds_config.items():
        output_path = os.path.join(sounds_dir, f"{filename}.wav")
        write_wave_file(output_path, freqs)
        
    logger.info("Successfully generated sound theme audio files")
