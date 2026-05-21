import sys
import re
import json
import argparse
import collections
from datetime import datetime, timezone
from pathlib import Path

TS_PATTERNS = [
    (re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})'),
     lambda m: datetime.fromisoformat(m.group(0).replace('Z', '+00:00'))),
    (re.compile(r'^(\d{4})/(\d{2})/(\d{2})\s+(\d{2}):(\d{2}):(\d{2})'),
     lambda m: datetime(*[int(x) for x in m.groups()], tzinfo=timezone.utc)),
    (re.compile(r'^(\d{1,2})-([A-Za-z]{3})-(\d{4})\s+(\d{2}):(\d{2}):(\d{2})'),
     lambda m: datetime.strptime(m.group(0), '%d-%b-%Y %H:%M:%S').replace(tzinfo=timezone.utc)),
    (re.compile(r'^(\d{10})\b'),
     lambda m: datetime.fromtimestamp(int(m.group(1)), tz=timezone.utc)),
]

def parse_timestamp(s):
    for pattern, converter in TS_PATTERNS:
        m = pattern.match(s)
        if m:
            try:
                return converter(m), m.end()
            except (ValueError, OverflowError):
                continue
    return None, 0

RT_MS   = re.compile(r'^(\d+(?:\.\d+)?)ms\b')
RT_SEC  = re.compile(r'^(\d+(?:\.\d+)?)s\b')
RT_BARE = re.compile(r'^(\d+(?:\.\d+)?)\b')

def parse_response_time(token):
    m = RT_MS.match(token)
    if m:
        return float(m.group(1))
    m = RT_SEC.match(token)
    if m:
        return float(m.group(1)) * 1000
    m = RT_BARE.match(token)
    if m:
        val = float(m.group(1))
        if val < 1_000_000:
            return val
    return None

HTTP_METHODS = {'GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS', 'TRACE', 'CONNECT'}

ENTRY = collections.namedtuple(
    'Entry',
    ['ts', 'ip', 'method', 'path', 'status', 'response_ms', 'raw']
)

def parse_line(raw):
    line = raw.strip()
    if not line:
        return None
    if line.startswith('{'):
        try:
            obj = json.loads(line)
            ts_raw = (obj.get('timestamp') or obj.get('time') or
                      obj.get('ts') or obj.get('@timestamp') or '')
            ip      = obj.get('ip') or obj.get('remote_addr') or obj.get('client') or ''
            method  = (obj.get('method') or obj.get('verb') or '').upper()
            path    = obj.get('path') or obj.get('url') or obj.get('uri') or ''
            status  = obj.get('status') or obj.get('status_code') or obj.get('code')
            rt_raw  = str(obj.get('response_time') or obj.get('duration') or
                          obj.get('latency') or '')

            ts, _ = parse_timestamp(str(ts_raw)) if ts_raw else (None, 0)
            try:
                status_int = int(status) if status not in (None, '-', '') else None
            except (ValueError, TypeError):
                status_int = None

            rt_ms = parse_response_time(rt_raw) if rt_raw else None

            if method in HTTP_METHODS and path:
                return ENTRY(ts, ip, method, path, status_int, rt_ms, raw)
        except json.JSONDecodeError:
            pass
        return None

    tokens = tokenise(line)
    if not tokens:
        return None

    ts, consumed, tokens = extract_timestamp(tokens, line)
    ip     = extract_ip(tokens)
    method = extract_method(tokens)
    path   = extract_path(tokens, method)
    status = extract_status(tokens)
    rt_ms  = extract_response_time(tokens)

    if not method or not path:
        return None

    return ENTRY(ts, ip, method, path, status, rt_ms, raw)

def tokenise(line):
    tokens = []
    for m in re.finditer(r'"[^"]*"|\'[^\']*\'|\S+', line):
        tokens.append(m.group(0))
    return tokens

def extract_timestamp(tokens, original_line):
    if not tokens:
        return None, 0, tokens
    ts, consumed = parse_timestamp(tokens[0])
    if ts:
        return ts, consumed, tokens[1:]
    if len(tokens) >= 2:
        combined = tokens[0] + ' ' + tokens[1]
        ts, consumed = parse_timestamp(combined)
        if ts:
            return ts, consumed, tokens[2:]
    return None, 0, tokens

def extract_ip(tokens):
    ip_re = re.compile(
        r'^(\d{1,3}\.){3}\d{1,3}$'
        r'|^[0-9a-fA-F:]{3,39}$'
    )
    for t in tokens:
        if ip_re.match(t):
            return t
    return ''

def extract_method(tokens):
    for t in tokens:
        if t.upper() in HTTP_METHODS:
            return t.upper()
    return ''

def extract_path(tokens, method):
    if not method:
        return ''
    for i, t in enumerate(tokens):
        if t.upper() == method and i + 1 < len(tokens):
            candidate = tokens[i + 1]
            if candidate.startswith('/') or candidate.startswith('http'):
                return candidate.split('?')[0]
    for t in tokens:
        if t.startswith('/'):
            return t.split('?')[0]
    return ''

def extract_status(tokens):
    for t in tokens:
        if t == '-':
            return None
        if re.match(r'^[1-5]\d{2}$', t):
            return int(t)
    return None

def extract_response_time(tokens):
    result = None
    for t in tokens:
        v = parse_response_time(t)
        if v is not None:
            result = v
    return result

def buildreport(entries, parse_errors, total_lines):
    ok = [e for e in entries if e.status is not None]
    status_counter  = collections.Counter(e.status for e in ok)
    method_counter  = collections.Counter(e.method for e in entries)
    ip_counter      = collections.Counter(e.ip for e in entries if e.ip)
    error_by_path = collections.Counter(
        e.path for e in ok if e.status and e.status >= 400
    )
    rt_entries = [e for e in entries if e.response_ms is not None]
    path_times = collections.defaultdict(list)
    for e in rt_entries:
        normalised = re.sub(r'/\d+', '/{id}', e.path)
        path_times[normalised].append(e.response_ms)
    slow_paths = sorted(
        [(p, sum(ts)/len(ts), max(ts), len(ts)) for p, ts in path_times.items()],
        key=lambda x: x[1], reverse=True
    )
    hourly = collections.Counter()
    for e in entries:
        if e.ts:
            hourly[e.ts.strftime('%Y-%m-%d %H:00')] += 1
    suspicious = collections.Counter(
        e.ip for e in ok if e.ip and e.status and e.status >= 400
    )
    return {
        'total_lines'    : total_lines,
        'parsed_ok'      : len(entries),
        'parse_errors'   : parse_errors,
        'status_counter' : status_counter,
        'method_counter' : method_counter,
        'ip_counter'     : ip_counter,
        'error_by_path'  : error_by_path,
        'slow_paths'     : slow_paths,
        'hourly_traffic' : hourly,
        'suspicious_ips' : suspicious,
    }

def printreport(report, top_n=10):
    def section(title):
        print(f'  {title}')
    parsed  = report['parsed_ok']
    errors  = report['parse_errors']
    total   = report['total_lines']
    skipped = total - parsed - errors
    section('OVERVIEW')
    print(f'  Total lines read   : {total:,}')
    print(f'  Successfully parsed: {parsed:,}  ({100*parsed/max(total,1):.1f}%)')
    print(f'  Unparseable lines  : {errors:,}  (logged below)')
    if skipped > 0:
        print(f'  Blank / skipped    : {skipped:,}')
    section('HTTP STATUS CODES')
    for code, count in sorted(report['status_counter'].items()):
        bar = '█' * min(40, count * 40 // max(report['status_counter'].values()))
        print(f'  {code}  {bar:<40}  {count:,}')
    section('HTTP METHODS')
    for method, count in report['method_counter'].most_common():
        print(f'  {method:<8}  {count:,}')
    section(f'TOP {top_n} ENDPOINTS BY ERROR RATE')
    for path, count in report['error_by_path'].most_common(top_n):
        print(f'  {count:>6,}  errors   {path}')
    section(f'TOP {top_n} SLOWEST ENDPOINTS (by avg response time)')
    print(f'  {"Endpoint":<45} {"Avg ms":>8} {"Max ms":>8} {"Hits":>7}')
    for path, avg, mx, n in report['slow_paths'][:top_n]:
        print(f'  {path:<45} {avg:>8.1f} {mx:>8.1f} {n:>7,}')
    section(f'TOP {top_n} CLIENT IPs')
    for ip, count in report['ip_counter'].most_common(top_n):
        print(f'  {ip:<20}  {count:,} requests')
    section(f'TOP {top_n} IPs WITH MOST ERRORS (potential scanners / bad clients)')
    for ip, count in report['suspicious_ips'].most_common(top_n):
        print(f'  {ip:<20}  {count:,} errors')
    if report['hourly_traffic']:
        section('HOURLY TRAFFIC (most active hours)')
        peak = report['hourly_traffic'].most_common(top_n)
        max_count = peak[0][1] if peak else 1
        for hour, count in sorted(peak):
            bar = '█' * (count * 30 // max_count)
            print(f'  {hour}   {bar:<30}  {count:,}')
    
def main():
    parser = argparse.ArgumentParser(
        description='Analyze a server log file and print a summary report.'
    )
    parser.add_argument('logfile', help='Path to the log file')
    parser.add_argument(
        '--top', type=int, default=10,
        help='How many items to show in ranked lists (default: 10)'
    )
    parser.add_argument(
        '--show-bad', action='store_true',
        help='Print the first 20 unparseable lines at the end of the report'
    )
    args = parser.parse_args()
    path = Path(args.logfile)
    if not path.exists():
        sys.exit(f'error: file not found: {path}')
    if not path.is_file():
        sys.exit(f'error: not a regular file: {path}')
    entries      = []
    bad_lines    = []
    total_lines  = 0
    with open(path, encoding='utf-8', errors='replace') as fh:
        for raw in fh:
            total_lines += 1
            entry = parse_line(raw)
            if entry is not None:
                entries.append(entry)
            else:
                stripped = raw.strip()
                if stripped:
                    bad_lines.append((total_lines, stripped))
    report = buildreport(entries, len(bad_lines), total_lines)
    printreport(report, top_n=args.top)
    if args.show_bad and bad_lines:
        print('SAMPLE UNPARSEABLE LINES (first 20)')
        for lineno, line in bad_lines[:20]:
            print(f'  line {lineno:>6}: {line[:120]}')
        print()

if __name__ == '__main__':
    main()