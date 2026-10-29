"""Bounded audio decoding using the PyAV libraries already shipped for Whisper."""
import io
import time


def decode_audio(content,max_seconds=120):
    import av
    import numpy as np
    if not isinstance(content,bytes) or not content or len(content)>20*1024*1024:
        raise ValueError('Audio must be non-empty and under 20 MB.')
    chunks=[];samples=0;deadline=time.monotonic()+15
    try:
        with av.open(io.BytesIO(content),mode='r') as container:
            if not container.streams.audio:raise ValueError('No audio stream was found.')
            resampler=av.AudioResampler(format='fltp',layout='mono',rate=16000)
            for frame in container.decode(audio=0):
                if time.monotonic()>deadline:raise ValueError('Audio decoding timed out.')
                for output in resampler.resample(frame):
                    values=output.to_ndarray().reshape(-1)
                    samples+=values.size
                    if samples>max_seconds*16000:raise ValueError(f'Audio must be at most {max_seconds} seconds.')
                    chunks.append(values)
            for output in resampler.resample(None):
                values=output.to_ndarray().reshape(-1);samples+=values.size
                if samples>max_seconds*16000:raise ValueError(f'Audio must be at most {max_seconds} seconds.')
                chunks.append(values)
    except av.error.FFmpegError:raise ValueError('Could not decode this audio file.') from None
    result=np.concatenate(chunks).astype('float32') if chunks else np.empty(0,dtype='float32')
    if not result.size or not np.isfinite(result).all():raise ValueError('Audio contains no valid samples.')
    return result
