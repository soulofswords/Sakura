"""Validate inference results before a WAV writer receives them."""
def require_audio(result):
    # rvc-python returns a numpy array on success, but an (error, (None,None))
    # tuple on failure. Never let that tuple obscure the real inference error.
    if isinstance(result, tuple):
        raise RuntimeError('RVC inference failed before producing audio. Check the RVC service log for the underlying model or runtime error.')
    if not hasattr(result,'dtype') or getattr(result,'size',0)==0:
        raise RuntimeError('RVC inference returned no audio samples.')
    return result
