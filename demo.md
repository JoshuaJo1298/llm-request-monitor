# Incident walkthrough

1. Start the app and import the incident as described in the [README](README.md).
2. In the 1-hour window, compare `aurora-large` at 3,014 ms p95 against the faster `aurora-small`. Both received 48 requests, and only `aurora-large` recorded failures.
3. Apply the 15-minute filter to isolate the recent burst. Re-import the file and check that the request counts are unchanged.
