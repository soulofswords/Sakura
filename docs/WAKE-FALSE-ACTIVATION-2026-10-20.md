# Sakura Mobile 0.3.11 — false wake activation correction

The previous detector accepted repeated partial guesses from a phrase-constrained recognizer. This can force unrelated audio into a known phrase, opening the command window without an intentional wake phrase. The screenshot alone cannot establish the exact audio event, but this permissive path was present in the code.

- Removed all partial-result activation. Only a completed exact wake phrase can become a candidate.
- Before opening the command microphone or calling any AI, confirm the candidate with unrestricted offline recognition of the same bounded in-memory audio. Require exact phrase/word count, per-word confidence >=0.85, mean >=0.92 and plausible 0.35–4.5-second phrase duration.
- Keep bounded audio overlap between endpoints so silence boundaries do not cut the first wake word off, including after long idle periods. Audio is not written to a file or uploaded for verification. Unrestricted confirmation runs only for completed wake candidates.
- Discard filler-only commands such as huh, uh, um and hmm. One valid wake confirmation permits one question window; empty/filler results return silently to wake listening without an AI request.
- Applied equivalent completed-phrase/unrestricted-confirmation/filler checks to Windows Companion local copies. No Windows installer or GitHub release was changed.

Validation: actual Java confidence/word/duration/filler cases passed. Actual Windows offline decoder exercised with synthesized Hey Sakura followed by What time is it, and separately huh/unrelated speech without wake. Positive still activates after long initial silence; negative inputs produce zero questions. No real microphone was accessed. Android compilation/R8/signature/archive checks and packaged browser regression passed.

Real phone room audio/accents/TV/locked-screen recognition remain unverified; no universal zero-false-trigger guarantee. This is a stricter offline speech detector, not a trained hardware wake engine.

Install over the existing Sakura Mobile; the offline pack does not need redownloading.
SHA256: f1b17592a26a69261327342692272647d50ce6100a5b92e49b65beb90b5c9e52
