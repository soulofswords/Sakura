"""Owner-facing speaker enrolment; shared encrypted profile store, no new listener."""
from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool


def install(app, allowed):
    from agent_runtime import runtime
    from speaker_profiles import SpeakerProfiles
    speakers = SpeakerProfiles(runtime.store_path.parent / 'voiceprint')

    def check():
        if not allowed():
            raise HTTPException(409, 'Voice enrolment requires Companion mode.')

    @app.get('/api/companion/speakers')
    async def status():
        check()
        return await run_in_threadpool(speakers.status)

    @app.post('/api/companion/speakers/install')
    async def setup(payload: dict):
        check()
        if payload.get('consent') is not True:
            raise HTTPException(400, 'Confirm the optional recognition download.')
        return await run_in_threadpool(speakers.install)

    @app.post('/api/companion/speakers/enroll')
    async def enroll(request: Request, name: str):
        check()
        audio = bytearray()
        async for chunk in request.stream():
            audio.extend(chunk)
            if len(audio) > 5_000_000:
                raise HTTPException(413, 'Use a WAV recording under 5 MB.')
        try:
            return await run_in_threadpool(speakers.enroll, name, bytes(audio))
        except ValueError as error:
            raise HTTPException(400, str(error)) from error

    @app.post('/api/companion/speakers/rename')
    async def rename(payload: dict):
        check()
        try:
            return await run_in_threadpool(speakers.rename, payload.get('name'), payload.get('new_name'))
        except (ValueError, TypeError) as error:
            raise HTTPException(400, str(error)) from error

    @app.delete('/api/companion/speakers/{name}')
    async def forget(name: str):
        check()
        return await run_in_threadpool(speakers.forget, name)
