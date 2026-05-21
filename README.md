Log Analyzer

A CLI tool that reads a server log file and prints a report covering traffic
patterns, slow endpoints, error rates, suspicious IPs, and a digest of lines
that couldn't be parsed.

No external dependencies. Runs on any machine with Python 3.8+.

--------------------------------------------------------------------------------
Quick start

1. clone / unzip the repo, then:
cd Log-Analyzer

3. Analyze it
python analyze.py sample.log

That's it. No pip install, no virtualenv, no config files.

----------------------------------------------------------------------------------
Generating test data

python scripts/generate_logs.py
python scripts/generate_logs.py -n 50000 -o big.log

The generator deliberately mixes in the same edge cases the analyzer handles:
four different timestamp formats, three response-time units, missing status
codes (-), JSON-formatted lines, stack-trace fragments, partial writes, and
blank lines. Run it, open the file in a text editor, and you'll see the mess.

-------------------------------------------------------------------------------------
Running the analyzer

python analyze.py sample.log --show-bad

-------------------------------------------------------------------------------------
Examples

basic report
python analyze.py sample.log

show top 20 in each list, and dump bad lines
python analyze.py sample.log --top 20 --show-bad

pipe through less if the output is long
python analyze.py big.log --show-bad | less

--------------------------------------------------------------------------------------
What the report contains

Overview: total lines, parse rate, error count 
HTTP status codes: distribution with an ASCII bar chart 
HTTP methods: GET vs POST vs etc. 
Top endpoints by error rate: which paths generate the most 4xx/5xx 
Slowest endpoints: avg and max response time, grouped by path pattern 
Top client IPs: highest request volume 
IPs with most errors: potential scanners or misconfigured clients 
Hourly traffic: busiest hours of the day 

--------------------------------------------------------------------------------------
Requirements

- Python 3.8 or newer
- No third-party packages

Tested on macOS 14, Ubuntu 22.04, and Windows 11 (PowerShell + WSL).