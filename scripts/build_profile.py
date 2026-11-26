"""Builds the profile SVG shown in README.md.

Runs daily in GitHub Actions (see .github/workflows/profile.yml). Uses only the
standard library. Live data (uptime, repos, stars, commits, contributions,
languages, streaks) comes from the GitHub GraphQL API; everything else is in
PROFILE below.

    python scripts/build_profile.py --out dist/profile.svg [--snake dist/snake.svg]
    python scripts/build_profile.py --out x.svg --data cache.json   # offline
"""
import argparse, base64, datetime as dt, html, json, os, re, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
USER = os.environ.get("GH_USER", "MeetAghara512")

PROFILE = {
    "name": "Meet Aghara",
    "tagline": "[ Fast Code AI · Bengaluru ]",
    "info": [("Role", "Software Development Engineer"), ("Company", "Fast Code AI"), ("Previously", "Samsung R&D, SDE intern"),
             ("Location", "Bengaluru, India"), ("Uptime", "{uptime}"), ("Focus", "Backend, Real-time, Applied AI")],
    "contact": [("GitHub", f"github.com/{USER}"), ("LinkedIn", "linkedin.com/in/meetaghara512")],
    "competitive": [("Codeforces", "Expert · 1630"), ("LeetCode", "Knight · 1965"), ("CodeChef", "4-star · 1851"), ("Solved", "1100+ problems")],
    "projects": [("ShareThings", "P2P video & screen share over WebRTC · 5k users", True),
                 ("DriveMyWay", "Car rental platform: booking, payments, dashboards", True),
                 ("Insight-360-R", "Research papers to slides, podcasts, flowcharts", False),
                 ("KitchenSense-AI", "Vision inventory and food-waste forecasting", False),
                 ("CPU Scheduler", "Animated Gantt charts for OS scheduling", False)],
}
QUOTES = [
    ("Talk is cheap. Show me the code.", "Linus Torvalds"),
    ("Simplicity is prerequisite for reliability.", "Edsger W. Dijkstra"),
    ("Programs must be written for people to read, and only incidentally for machines to execute.", "Harold Abelson"),
    ("Make it work, make it right, make it fast.", "Kent Beck"),
    ("Any fool can write code that a computer can understand. Good programmers write code that humans can understand.", "Martin Fowler"),
    ("Before software can be reusable it first has to be usable.", "Ralph Johnson"),
    ("Premature optimization is the root of all evil.", "Donald Knuth"),
    ("First, solve the problem. Then, write the code.", "John Johnson"),
    ("The best error message is the one that never shows up.", "Thomas Fuchs"),
    ("Deleted code is debugged code.", "Jeff Sickel"),
]
IGNORE_LANGS = {"Cython", "XSLT", "PowerShell", "Batchfile", "Shell", "Dockerfile", "Makefile", "CMake", "Procfile"}

# palette
BG, PANEL, BORDER, ACC = "#060606", "#0b0b0b", "#252525", "#c5ff4a"
TEXT, MUTED, LABEL, DOTS, VAL, STAT, FIRE = "#e5e5e5", "#8b949e", "#ffa657", "#484f58", "#f0f6fc", "#79c0ff", "#ff9a1f"
SANS, SANS5, SANS7, MONO, MONO7 = "dmsans-400", "dmsans-500", "dmsans-700", "jbmono-400", "jbmono-700"
W = 800
METRICS = json.load(open(os.path.join(HERE, "fonts", "metrics.json"), encoding="utf-8"))

def tw(font, s, size): return sum(METRICS[font].get(c, 0.6) for c in s) * size
def esc(s): return html.escape(s, quote=False)
def text(x, y, s, font, size, fill, anchor="start", ls=0, extra=""):
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    l = f' letter-spacing="{ls}"' if ls else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" font-family="{font}" font-size="{size}" fill="{fill}"{a}{l}{extra}>{esc(s)}</text>'

# ---------------------------------------------------------------- data
def gql(query, variables, use_gh):
    body = json.dumps({"query": query, "variables": variables})
    if use_gh:
        import subprocess
        out = subprocess.run(["gh", "api", "graphql", "--input", "-"], input=body, capture_output=True, text=True, check=True).stdout
        return json.loads(out)["data"]
    req = urllib.request.Request("https://api.github.com/graphql", body.encode(),
                                 {"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}", "Content-Type": "application/json"})
    res = json.load(urllib.request.urlopen(req, timeout=30))
    if "errors" in res: raise SystemExit(res["errors"])
    return res["data"]

def fetch(use_gh):
    q1 = """query($l:String!){user(login:$l){createdAt followers{totalCount}
      repositories(ownerAffiliations:OWNER,isFork:false,privacy:PUBLIC,first:100){totalCount nodes{stargazerCount
        languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}}}}}"""
    u = gql(q1, {"l": USER}, use_gh)["user"]
    q2 = """query($l:String!,$f:DateTime!,$t:DateTime!){user(login:$l){contributionsCollection(from:$f,to:$t){
      totalCommitContributions contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""
    now = dt.datetime.now(dt.timezone.utc); start = dt.datetime.fromisoformat(u["createdAt"].replace("Z", "+00:00"))
    years = []
    for y in range(start.year, now.year + 1):
        f = max(start, dt.datetime(y, 1, 1, tzinfo=dt.timezone.utc)); t = min(now, dt.datetime(y, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc))
        years.append(gql(q2, {"l": USER, "f": f.isoformat(), "t": t.isoformat()}, use_gh)["user"]["contributionsCollection"])
    return {"user": u, "years": years, "today": now.date().isoformat()}

def compute(d):
    u, today = d["user"], dt.date.fromisoformat(d["today"])
    created = dt.date.fromisoformat(u["createdAt"][:10])
    # uptime
    y, m, dd = today.year - created.year, today.month - created.month, today.day - created.day
    if dd < 0:
        m -= 1; prev = (today.replace(day=1) - dt.timedelta(days=1)); dd += prev.day
    if m < 0: y -= 1; m += 12
    pl = lambda n, w: f"{n} {w}{'' if n == 1 else 's'}"
    uptime = ", ".join([pl(y, "year"), pl(m, "month"), pl(dd, "day")])
    # contributions + streaks
    days = {}
    for yr in d["years"]:
        for w in yr["contributionCalendar"]["weeks"]:
            for c in w["contributionDays"]: days[c["date"]] = c["contributionCount"]
    days = dict(sorted((k, v) for k, v in days.items() if k <= d["today"]))
    order = list(days)
    longest = (0, None, None); run = 0; run_start = None
    for k in order:
        if days[k] > 0:
            run_start = run_start if run else k; run += 1
            if run > longest[0]: longest = (run, run_start, k)
        else: run = 0
    cur, i = 0, len(order) - 1
    if i >= 0 and days[order[i]] == 0: i -= 1  # today not counted yet
    cur_end = order[i] if i >= 0 else None
    while i >= 0 and days[order[i]] > 0: cur += 1; i -= 1
    cur_start = order[i + 1] if cur else None
    # languages: every repo weighs the same, so one huge repo can't swamp the bar
    share, colors = {}, {}
    for r in u["repositories"]["nodes"]:
        edges = [e for e in r["languages"]["edges"] if e["node"]["name"] not in IGNORE_LANGS]
        tot = sum(e["size"] for e in edges)
        for e in edges:
            n = "Python" if e["node"]["name"] == "Jupyter Notebook" else e["node"]["name"]; share[n] = share.get(n, 0) + e["size"] / tot
            colors[n] = e["node"]["color"] or "#8b949e"
    tot_all = sum(share.values()) or 1
    top = [kv for kv in sorted(share.items(), key=lambda kv: -kv[1]) if kv[1] / tot_all >= 0.02][:6]; s = sum(v for _, v in top)
    langs = [(n, v / s * 100, colors[n]) for n, v in top]
    weeks = d["years"][-1]["contributionCalendar"]["weeks"] if d["years"] else []
    return {"uptime": uptime, "repos": u["repositories"]["totalCount"], "stars": sum(r["stargazerCount"] for r in u["repositories"]["nodes"]),
            "followers": u["followers"]["totalCount"], "commits": sum(yr["totalCommitContributions"] for yr in d["years"]),
            "total": sum(days.values()), "since": order[0] if order else d["today"], "today": today,
            "cur": (cur, cur_start, cur_end), "longest": longest, "langs": langs, "weeks": weeks}

# ---------------------------------------------------------------- drawing
def fmt_date(s, year=True):
    d = dt.date.fromisoformat(s); return d.strftime("%b ") + str(d.day) + (d.strftime(", %Y") if year else "")

def section(y, h, title):
    return (f'<rect x="16.5" y="{y+.5}" width="{W-33}" height="{h-1}" fill="{PANEL}" stroke="{BORDER}"/>'
            + text(40, y + 30, f"[ {title} ]", SANS5, 11, MUTED, ls=2.4))

def lime_bar(y): return f'<rect x="0" y="{y}" width="{W}" height="1" fill="{BORDER}"/><rect x="0" y="{y+8}" width="{W}" height="3" fill="{ACC}"/>'

COLS = 44  # mono characters per info column
def kv(x, y, k, v, vcol=VAL, cols=COLS):
    dots = "." * max(3, cols - len(k) - len(v) - 5)
    return (f'<text x="{x}" y="{y}" font-family="{MONO}" font-size="13.5" xml:space="preserve">'
            f'<tspan fill="{ACC}">. </tspan><tspan fill="{LABEL}">{esc(k)}:</tspan><tspan fill="{DOTS}"> {dots} </tspan><tspan fill="{vcol}">{esc(v)}</tspan></text>')

def head(x, y, s, cols=COLS):
    rest = "─" * (cols - len(s) - 3)
    return (f'<text x="{x}" y="{y}" font-family="{MONO}" font-size="13.5" xml:space="preserve"><tspan fill="{DOTS}">─ </tspan>'
            f'<tspan fill="{ACC}" font-family="{MONO7}">{esc(s)}</tspan><tspan fill="{DOTS}"> {rest}</tspan></text>')

def build(c, snake_svg):
    out, y = [], 0
    # header with typewriter name
    name, nsize = PROFILE["name"], 28
    steps = [0] + [tw(SANS5, name[:i + 1], nsize) for i in range(len(name))]
    vals = ";".join(f"{v:.1f}" for v in steps); dur = len(name) * 0.09
    out.append(f'<defs><clipPath id="tw"><rect x="24" y="10" height="50" width="0"><animate attributeName="width" values="{vals}" dur="{dur:.2f}s" calcMode="discrete" fill="freeze"/></rect></clipPath></defs>')
    out.append(f'<g clip-path="url(#tw)">{text(24, 46, name, SANS5, nsize, "#ffffff")}</g>')
    cx = ";".join(f"{24 + v + 3:.1f}" for v in steps)
    out.append(f'<rect y="24" width="2" height="27" fill="{ACC}" x="27"><animate attributeName="x" values="{cx}" dur="{dur:.2f}s" calcMode="discrete" fill="freeze"/>'
               f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1s" begin="{dur:.2f}s" repeatCount="indefinite"/></rect>')
    out.append(text(24, 74, f"@{USER}", MONO, 14, ACC))
    out.append(text(W - 24, 44, PROFILE["tagline"], SANS, 13, MUTED, "end"))
    out.append(lime_bar(86)); y = 112

    # terminal info: two columns
    L, R, ly = 30, 418, y + 34
    rows_l = [head(L, ly, f"{USER.lower()}@github")]
    for i, (k, v) in enumerate(PROFILE["info"]): rows_l.append(kv(L, ly + 20 * (i + 1), k, v.format(uptime=c["uptime"])))
    base = ly + 20 * (len(PROFILE["info"]) + 2)
    rows_l.append(head(L, base, "Contact"))
    for i, (k, v) in enumerate(PROFILE["contact"]): rows_l.append(kv(L, base + 20 * (i + 1), k, v))
    rows_r = [head(R, ly, "Competitive")]
    for i, (k, v) in enumerate(PROFILE["competitive"]): rows_r.append(kv(R, ly + 20 * (i + 1), k, v, STAT))
    b2 = ly + 20 * (len(PROFILE["competitive"]) + 2)
    rows_r.append(head(R, b2, "GitHub Stats"))
    half = 21
    rows_r.append(kv(R, b2 + 20, "Repos", str(c["repos"]), STAT, half) + kv(R + 8.1 * (half + 2), b2 + 20, "Stars", str(c["stars"]), STAT, half))
    for i, (k, v) in enumerate([("Commits", f'{c["commits"]:,}'), ("Contributions", f'{c["total"]:,}'), ("Followers", str(c["followers"]))]):
        rows_r.append(kv(R, b2 + 20 * (i + 2), k, v, STAT))
    h_info = max(base + 20 * len(PROFILE["contact"]), b2 + 20 * 4) - y + 26
    out.append(f'<rect x="16.5" y="{y+.5}" width="{W-33}" height="{h_info-1}" fill="{PANEL}" stroke="{BORDER}"/>')
    out.append(f'<rect x="402" y="{y+18}" width="1" height="{h_info-36}" fill="{BORDER}"/>')
    out += rows_l + rows_r; y += h_info + 16

    # top languages
    h = 150; out.append(section(y, h, "TOP LANGUAGES"))
    bx, bw, x = 40, W - 80, 40
    for i, (n, p, col) in enumerate(c["langs"]):
        seg = bw * p / 100
        out.append(f'<rect x="{x:.1f}" y="{y+50}" width="{max(seg-3, 2):.1f}" height="8" rx="1.5" fill="{col}"/>'); x += seg
        lx, ly2 = (40 if i % 2 == 0 else 420), y + 84 + (i // 2) * 24
        out.append(f'<circle cx="{lx+4}" cy="{ly2-4}" r="4" fill="{col}"/>')
        out.append(f'<text x="{lx+16}" y="{ly2}" font-family="{SANS}" font-size="13" fill="{TEXT}">{esc(n)} <tspan fill="{MUTED}">{p:.0f}%</tspan></text>')
    y += h + 16

    # technologies (skillicons.dev artwork)
    sk = open(os.path.join(HERE, "skills.svg"), encoding="utf-8").read()
    vb = re.search(r'viewBox="([^"]+)"', sk).group(1); vw, vh = map(float, vb.split()[2:])
    inner = sk[sk.index(">", sk.index("<svg")) + 1: sk.rindex("</svg>")]
    iw = W - 80; ih = iw * vh / vw; h = int(ih + 78)
    out.append(section(y, h, "TECHNOLOGIES & SKILLS"))
    out.append(f'<svg x="40" y="{y+50}" width="{iw}" height="{ih:.1f}" viewBox="{vb}">{inner}</svg>'); y += h + 16

    # projects (compact)
    h = 52 + 20 * len(PROFILE["projects"]) + 8; out.append(section(y, h, "PROJECTS"))
    for i, (n, desc, live) in enumerate(PROFILE["projects"]):
        yy = y + 58 + 20 * i; tail = " · live" if live else ""
        dots = "." * max(3, 88 - len(n) - len(desc) - len(tail) - 5)
        out.append(f'<text x="40" y="{yy}" font-family="{MONO}" font-size="13.5" xml:space="preserve"><tspan fill="{ACC}">. </tspan><tspan fill="{LABEL}">{esc(n)}</tspan>'
                   f'<tspan fill="{DOTS}"> {dots} </tspan><tspan fill="{VAL}">{esc(desc)}</tspan><tspan fill="{ACC}">{tail}</tspan></text>')
    y += h + 6; out.append(lime_bar(y)); y += 26

    # streak stats
    h = 190; out.append(section(y, h, "GITHUB STREAK STATS"))
    cy = y + 112; cols = [W * 0.2 + 8, W / 2, W * 0.8 - 8]
    out.append(f'<rect x="{W*0.35:.0f}" y="{y+60}" width="1" height="104" fill="{BORDER}"/><rect x="{W*0.65:.0f}" y="{y+60}" width="1" height="104" fill="{BORDER}"/>')
    out.append(text(cols[0], cy - 8, f'{c["total"]:,}', SANS7, 28, VAL, "middle"))
    out.append(text(cols[0], cy + 20, "Total Contributions", SANS5, 13, TEXT, "middle"))
    out.append(text(cols[0], cy + 42, f'{fmt_date(c["since"])} - Present', SANS, 11, MUTED, "middle"))
    n, s0, s1 = c["cur"]
    out.append(f'<circle cx="{cols[1]}" cy="{cy-22}" r="34" fill="none" stroke="{FIRE}" stroke-width="5" stroke-dasharray="190 24" transform="rotate(-70 {cols[1]} {cy-22})"/>')
    fx, fy = cols[1], cy - 55
    out.append(f'<path d="M{fx},{fy-11} C{fx+7},{fy-4} {fx+8},{fy+3} {fx+5},{fy+8} C{fx+3},{fy+11} {fx-3},{fy+11} {fx-5},{fy+8} C{fx-8},{fy+3} {fx-5},{fy-2} {fx-2},{fy-5} C{fx-1},{fy-1} {fx+1},{fy} {fx+2},{fy-2} C{fx+2},{fy-6} {fx},{fy-9} {fx},{fy-11}Z" fill="{FIRE}">'
               f'<animate attributeName="opacity" values="1;.7;1" dur="1.4s" repeatCount="indefinite"/></path>')
    out.append(text(cols[1], cy - 12, str(n), SANS7, 28, VAL, "middle"))
    out.append(text(cols[1], cy + 32, "Current Streak", SANS7, 13, FIRE, "middle"))
    out.append(text(cols[1], cy + 52, f"{fmt_date(s0, False)} - {fmt_date(s1, False)}" if n else "Start one today", SANS, 11, MUTED, "middle"))
    ln, l0, l1 = c["longest"]
    out.append(text(cols[2], cy - 8, str(ln), SANS7, 28, VAL, "middle"))
    out.append(text(cols[2], cy + 20, "Longest Streak", SANS5, 13, TEXT, "middle"))
    out.append(text(cols[2], cy + 42, f"{fmt_date(l0)} - {fmt_date(l1)}" if ln else "—", SANS, 11, MUTED, "middle"))
    y += h + 6; out.append(lime_bar(y)); y += 26

    # contribution snake (or a static grid when running without the snake file)
    gw = W - 80
    if snake_svg:
        sv = re.sub(r"<\?xml[^>]*>", "", snake_svg).strip()
        vb = re.search(r'viewBox="([^"]+)"', sv).group(1); vw, vh = map(float, vb.split()[2:])
        gh = gw * vh / vw; inner = sv[sv.index(">", sv.index("<svg")) + 1: sv.rindex("</svg>")]
        body = f'<svg x="40" y="{{Y}}" width="{gw}" height="{gh:.1f}" viewBox="{vb}">{inner}</svg>'
    else:
        lv = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]; wk = c["weeks"][-52:]; cell = gw / 52; gh = cell * 7; cells = []
        mx = max([d["contributionCount"] for w in wk for d in w["contributionDays"]] + [1])
        for i, w in enumerate(wk):
            for d in w["contributionDays"]:
                k = 0 if not d["contributionCount"] else min(4, 1 + int(3 * d["contributionCount"] / mx))
                wd = dt.date.fromisoformat(d["date"]).isoweekday() % 7
                cells.append(f'<rect x="{40 + i*cell:.1f}" y="{{Y}}" width="{cell-3:.1f}" height="{cell-3:.1f}" rx="2" fill="{lv[k]}" transform="translate(0,{wd*cell:.1f})"/>')
        body = "".join(cells)
    h = int(gh + 82); out.append(section(y, h, "CONTRIBUTION SNAKE")); out.append(body.replace("{Y}", f"{y+52}")); y += h + 16

    # quote of the day
    q, a = QUOTES[c["today"].toordinal() % len(QUOTES)]
    words, lines, cur = q.split(), [], ""
    for wd in words:
        if tw(SANS, f"“{cur} {wd}”", 16) > W - 170 and cur: lines.append(cur); cur = wd
        else: cur = f"{cur} {wd}".strip()
    lines.append(cur); lines[0] = "“" + lines[0]; lines[-1] += "”"
    h = 120 + 24 * len(lines); out.append(section(y, h, "DEVELOPER QUOTE"))
    out.append(f'<rect x="40.5" y="{y+50.5}" width="{W-81}" height="{h-72}" rx="8" fill="#101010" stroke="{BORDER}"/>')
    out.append(f'<circle cx="{W-58}" cy="{y+68}" r="3" fill="{ACC}"><animate attributeName="opacity" values="1;.3;1" dur="2s" repeatCount="indefinite"/></circle>')
    out.append(text(62, y + 96, "”", SANS7, 34, ACC))
    for i, ln_ in enumerate(lines): out.append(text(92, y + 90 + 24 * i, ln_, SANS, 16, TEXT, extra=' font-style="italic"'))
    out.append(text(W - 62, y + 90 + 24 * len(lines) + 6, f"— {a}", SANS5, 12, MUTED, "end"))
    y += h + 16

    fonts = "".join(f'@font-face{{font-family:{f};src:url(data:font/woff2;base64,{base64.b64encode(open(os.path.join(HERE, "fonts", f + ".woff2"), "rb").read()).decode()}) format("woff2")}}'
                    for f in (SANS, SANS5, SANS7, MONO, MONO7))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{y}" viewBox="0 0 {W} {y}">'
            f'<style>{fonts}</style><rect width="{W}" height="{y}" fill="{BG}"/>{"".join(out)}</svg>')

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--snake"); ap.add_argument("--data")
    ap.add_argument("--gh", action="store_true", help="fetch through the gh CLI instead of GITHUB_TOKEN")
    a = ap.parse_args()
    if a.data and os.path.exists(a.data): data = json.load(open(a.data))
    else:
        data = fetch(a.gh)
        if a.data: json.dump(data, open(a.data, "w"))
    snake = open(a.snake, encoding="utf-8").read() if a.snake and os.path.exists(a.snake) else None
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    svg = build(compute(data), snake); open(a.out, "w", encoding="utf-8").write(svg)
    print(f"wrote {a.out} ({len(svg)//1024} KB)")
