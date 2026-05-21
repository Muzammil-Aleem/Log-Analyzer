Quick start

1. clone / unzip the repo, then:
cd Log-Analyzer

3. Analyze it
python analyze.py sample.log

That's it. No pip install, no virtualenv, no config files.

Generating test data

python scripts/generate_logs.py
python scripts/generate_logs.py -n 50000 -o big.log

The generator deliberately mixes in the same edge cases the analyzer handles:
four different timestamp formats, three response-time units, missing status
codes (-), JSON-formatted lines, stack-trace fragments, partial writes, and
blank lines. Run it, open the file in a text editor, and you'll see the mess.
