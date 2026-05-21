#Analyze
python analyze.py sample.log
#Unparseable lines
python analyze.py sample.log --show-bad

If you want to test against a file you already have:
python analyze.py /path/to/your/access.log

Nothing to install. Just Python.

-------------------------------------------------------------------------------------
Why Python, no dependencies:

The task is fundamentally text processing — reading lines, matching patterns,
counting things, printing a report. Python's standard library covers all of
that without any setup friction: `re`, `collections`, `datetime`, `json`,
`argparse`, `pathlib`. A reviewer on a fresh machine can run this in under
ten seconds.

I picked a CLI because that's what I'd actually want on call. A terminal
window on a production box (or in a CI pipeline) is where you need this
information; a web dashboard requires a running server, a browser, and trust
that the dashboard machine can reach the logs.

----------------------------------------------------------------------------------------
What would have been worse:

Node.js with multiple npm packages would have been a worse choice. You'd
need `npm install`, risk version conflicts, and the result would be three
hundred lines of async/await and callbacks to do the same string processing
that Python does in one loop. The runtime overhead is also higher for a
single-pass sequential file scan where there's nothing to parallelize.

Bash / awk would struggle with the JSON lines, multi-format timestamps,
and the need to group paths by normalised pattern (e.g. `/api/users/42` and
`/api/users/99` → `/api/users/{id}`). Possible, but the script would be
unmaintainable past about 150 lines.

-----------------------------------------------------------------------------------------
Two-token timestamps.

File: `analyze.py`, function `_extract_timestamp`, lines ~120–130.
Some timestamp formats span two whitespace-separated tokens:

```
2024/03/15 14:23:01   →  token 0: "2024/03/15"   token 1: "14:23:01"
15-Mar-2024 14:23:01  →  token 0: "15-Mar-2024"  token 1: "14:23:01"
```

`_extract_timestamp` first tries to parse just `tokens[0]`. If that fails,
it joins `tokens[0] + ' ' + tokens[1]` and tries again. Only after both
attempts fail does it give up and return `(None, 0, original_tokens)`.

Without this, a line like `2024/03/15 14:23:01 10.0.0.7 GET /api/users 200 142ms`
would fail to produce a timestamp and — more importantly — the `14:23:01`
token would be left in the list, where `_extract_ip` and `_extract_method`
would waste time trying to match it, and `_extract_response_time` might
accidentally interpret it as `14230.01 ms` if the bare-number branch
matched `14`. The parsed entry would have garbage timing data.

--------------------------------------------------------------------------------------
I used Claude (claude.ai) during development in two places:

a) Timestamp regex for Day-Mon-Year format

I asked: "what's the strptime format string for '15-Mar-2024 14:23:01'?"
It gave me `'%d-%b-%Y %H:%M:%S'`, which is correct. I used that directly.

b) Drafting the response-time normalisation logic

I asked for a function that converts `"142ms"`, `"0.142s"`, and bare `"142"`
to a float in milliseconds.

The AI's version accepted any bare number unconditionally, which would have
turned Unix epoch timestamps (ten-digit integers) into absurd millisecond
values whenever a line lacked an explicit `ms`/`s` suffix and the epoch
appeared in the wrong column. I added the sanity cap:

if val < 1_000_000:   
    return val

and changed the function to return `None` rather than a wrong number when
the cap is exceeded. A wrong number silently poisons the slow-endpoint
rankings; `None` is simply excluded from the average.

----------------------------------------------------------------------------
The path grouping is too naive.

Right now, `/api/users/42` and `/api/users/99` both normalise to
`/api/users/{id}` because I replace any run of digits with `{id}`. That
works for simple cases but falls apart with:

- UUIDs: `/api/orders/3fa85f64-5717-4562-b3fc-2c963f66afa6` — not matched
  by `\d+`, so every UUID gets its own row in the slow-endpoint table.
- Mixed segments: `/v2/tenants/acme/users/42` — only `42` gets replaced,
  leaving `acme` as a literal, so different tenants produce different rows.
- Query strings: I strip them before grouping, which is correct, but the
  strip happens in `_extract_path` rather than in the grouping step, so
  it's easy to accidentally break if someone refactors.

With another day I'd replace the regex substitution with a proper route
template matcher — either a small trie that learns patterns from the data
(grouping paths with the same structure even if they contain non-numeric
identifiers), or a configurable list of route templates supplied by the user
in a YAML file. The latter is the more practical solution for a real ops
tool because the people running it know their own route structure.