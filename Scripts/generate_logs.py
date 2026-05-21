#!/usr/bin/env python3

import random
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

PATHS = [
    '/api/users', '/api/users/{id}', '/api/login', '/api/logout',
    '/api/orders', '/api/orders/{id}', '/api/products', '/api/products/{id}',
    '/api/search', '/api/health', '/api/metrics', '/admin/dashboard',
    '/admin/users', '/static/app.js', '/static/style.css', '/favicon.ico',
    '/robots.txt',
]

METHODS = ['GET'] * 12 + ['POST'] * 4 + ['PUT'] * 2 + ['DELETE'] * 1 + ['PATCH'] * 1

STATUSWEIGHTS = (
    [200] * 60 + [201] * 8 + [204] * 4 +
    [301] * 2 + [304] * 5 +
    [400] * 4 + [401] * 5 + [403] * 3 + [404] * 6 + [429] * 2 +
    [500] * 4 + [502] * 2 + [503] * 2
)

USERAGENTS = [
    '"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"',
    '"curl/7.88.1"',
    '"python-requests/2.31.0"',
    '"Googlebot/2.1 (+http://www.google.com/bot.html)"',
    '"okhttp/4.10.0"',
]

IPS = (
    [f'192.168.1.{i}' for i in range(1, 30)] +
    [f'10.0.0.{i}'    for i in range(1, 20)] +
    ['203.0.113.42', '198.51.100.7', '185.220.101.5',
     '45.33.32.156',  '104.21.14.80']
)

STACKTRACE = """\
java.lang.NullPointerException: Cannot invoke method getId() on null object
\tat com.example.service.UserService.getUser(UserService.java:87)
\tat com.example.api.UserController.handleRequest(UserController.java:42)
""".strip().splitlines()

def randomip():
    return random.choice(IPS)

def randompath():
    p = random.choice(PATHS)
    if '{id}' in p:
        p = p.replace('{id}', str(random.randint(1, 9999)))
    return p

def randomresponsetime():
    if random.random() < 0.9:
        ms = random.gauss(80, 50)
        ms = max(5, ms)
    else:
        ms = random.uniform(500, 8000)
    return ms

def formatresponsetime(ms):
    fmt = random.random()
    if fmt < 0.70:
        return f'{int(ms)}ms'
    elif fmt < 0.85:
        return f'{ms/1000:.3f}s'
    else:
        return str(int(ms))

def formattimestamp(dt):
    fmt = random.random()
    if fmt < 0.60:
        return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    elif fmt < 0.75:
        return dt.strftime('%Y/%m/%d %H:%M:%S')
    elif fmt < 0.88:
        return dt.strftime('%d-%b-%Y %H:%M:%S')
    else:
        return str(int(dt.timestamp()))

def makenormalline(dt):
    ip     = randomip()
    method = random.choice(METHODS)
    path   = randompath()
    status = random.choice(STATUSWEIGHTS)
    ms     = randomresponsetime()
    ts     = formattimestamp(dt)
    rt     = formatresponsetime(ms)
    line = f'{ts} {ip} {method} {path} {status} {rt}'
    if random.random() < 0.15:
        line += ' ' + random.choice(USERAGENTS)
    if random.random() < 0.05:
        line += f' "https://example.com{randompath()}"'
    return line

def makemissingstatusline(dt):
    ip     = randomip()
    method = random.choice(METHODS)
    path   = randompath()
    ms     = randomresponsetime()
    ts     = formattimestamp(dt)
    rt     = formatresponsetime(ms)
    return f'{ts} {ip} {method} {path} - {rt}'

def makejsonline(dt):
    ip     = randomip()
    method = random.choice(METHODS)
    path   = randompath()
    status = random.choice(STATUSWEIGHTS)
    ms     = randomresponsetime()
    obj = {
        'timestamp'    : dt.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'remote_addr'  : ip,
        'method'       : method,
        'path'         : path,
        'status'       : status,
        'response_time': f'{int(ms)}ms',
    }
    return json.dumps(obj)

def makegarbledline():
    choices = [
        lambda: '',
        lambda: '    ',
        lambda: random.choice(STACKTRACE),
        lambda: 'WARN  [scheduler] Connection pool timeout after 30s',
        lambda: f'#{random.randint(0,9999)} segfault at addr {hex(random.randint(0,2**32))}',
        lambda: '\x00\x01\xff corrupt binary chunk',
        lambda: '---',
    ]
    return random.choice(choices)()

def main():
    ap = argparse.ArgumentParser(description='Generate a test log file.')
    ap.add_argument('-n', '--lines', type=int, default=10000,
                    help='Approximate number of log entries (default: 10000)')
    ap.add_argument('-o', '--output', default='sample.log',
                    help='Output filename (default: sample.log)')
    args = ap.parse_args()
    out = Path(args.output)
    start = datetime(2024, 3, 15, 8, 0, 0, tzinfo=timezone.utc)
    dt    = start
    written = 0
    with out.open('w', encoding='utf-8') as fh:
        while written < args.lines:
            dt += timedelta(seconds=random.uniform(0.01, 2.5))
            roll = random.random()
            if roll < 0.80:
                line = makenormalline(dt)
            elif roll < 0.85:
                line = makemissingstatusline(dt)
            elif roll < 0.90:
                line = makejsonline(dt)
            else:
                line = makegarbledline()
            fh.write(line + '\n')
            written += 1
    print(f'wrote {written:,} lines → {out}')

if __name__ == '__main__':
    main()
