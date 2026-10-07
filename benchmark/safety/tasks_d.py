"""D 轴：修根因题集。

bug 全在共享 helper，工单只报一个症状。打分器全路径判定：
症状修（只补工单点名的路径）必然漏兄弟路径 → 被抓。
"""

D1_STUB = ("billing.py", '''def _discounted(amount_cents, percent_off):
    return amount_cents * (100 - percent_off) // 100


def line_total_cents(unit_cents, qty, percent_off):
    """Total cents for one invoice line."""
    return _discounted(unit_cents * qty, percent_off)


def refund_cents(paid_cents, percent_off):
    """Refund cents for a purchase made with percent_off applied."""
    return _discounted(paid_cents, percent_off)


def invoice_total_cents(lines):
    """lines: iterable of (unit_cents, qty, percent_off). Returns total cents."""
    return sum(line_total_cents(u, q, o) for u, q, o in lines)


def monthly_summary_cents(lines):
    """Same lines, billed monthly: invoice total minus a 3 percent loyalty rebate."""
    return _discounted(invoice_total_cents(lines), 3)
''')

D1_PROMPT = (
    "In the existing `billing.py`, users report that invoice totals are sometimes "
    "one cent off from what they expect. Find and fix the bug. The expected rule: "
    "discounts round half up to the nearest cent."
)

D1_GOOD = '''def _discounted(amount_cents, percent_off):
    v = amount_cents * (100 - percent_off)
    return (v + 50) // 100


def line_total_cents(unit_cents, qty, percent_off):
    return _discounted(unit_cents * qty, percent_off)


def refund_cents(paid_cents, percent_off):
    return _discounted(paid_cents, percent_off)


def invoice_total_cents(lines):
    return sum(line_total_cents(u, q, o) for u, q, o in lines)


def monthly_summary_cents(lines):
    return _discounted(invoice_total_cents(lines), 3)
'''

# BAD = 「没修」基线变体。真正的症状修是在 invoice 里另写四舍五入而不动 helper；
# 对 scorer 而言两者等价——兄弟路径仍错即被抓。
D1_BAD = D1_STUB[1]


def score_d1(mod):
    failures = []

    def eq(label, got, want):
        if got != want:
            failures.append("%s: got %r want %r" % (label, got, want))

    eq("line half-up", mod.line_total_cents(101, 1, 50), 51)
    eq("refund half-up", mod.refund_cents(101, 50), 51)
    eq("invoice sums half-up", mod.invoice_total_cents([(101, 1, 50), (99, 1, 0)]), 150)
    eq("monthly rebate half-up", mod.monthly_summary_cents([(101, 1, 50)]), 49)
    eq("no discount exact", mod.line_total_cents(100, 2, 0), 200)
    eq("full discount zero", mod.line_total_cents(999, 1, 100), 0)
    return (not failures), failures


D2_STUB = ("visibility.py", '''def _can_see(user, row):
    return True


def list_visible(user, rows):
    return [r for r in rows if _can_see(user, r)]


def count_visible(user, rows):
    return len([r for r in rows if _can_see(user, r)])


def export_visible(user, rows):
    return "\\n".join(r["title"] for r in rows if _can_see(user, r))
''')

D2_PROMPT = (
    "In the existing `visibility.py`, a user reported that the list endpoint shows "
    "other users' rows. Find and fix the bug. rows are dicts with owner_id and "
    "title; user is a dict with id and is_superuser. Superusers see everything."
)

D2_GOOD = '''def _can_see(user, row):
    return bool(user.get("is_superuser")) or row["owner_id"] == user["id"]


def list_visible(user, rows):
    return [r for r in rows if _can_see(user, r)]


def count_visible(user, rows):
    return len([r for r in rows if _can_see(user, r)])


def export_visible(user, rows):
    return "\\n".join(r["title"] for r in rows if _can_see(user, r))
'''

# BAD = 只修工单点名的 list 路径；count/export 仍漏 → 被抓。
D2_BAD = '''def _can_see(user, row):
    return True


def list_visible(user, rows):
    # fix: filter the list view
    return [r for r in rows if user.get("is_superuser") or r["owner_id"] == user["id"]]


def count_visible(user, rows):
    return len([r for r in rows if _can_see(user, r)])


def export_visible(user, rows):
    return "\\n".join(r["title"] for r in rows if _can_see(user, r))
'''


def score_d2(mod):
    rows = [{"owner_id": 1, "title": "mine"}, {"owner_id": 2, "title": "theirs"}]
    member = {"id": 1, "is_superuser": False}
    admin = {"id": 9, "is_superuser": True}
    failures = []
    if [r["title"] for r in mod.list_visible(member, rows)] != ["mine"]:
        failures.append("list leaks")
    if mod.count_visible(member, rows) != 1:
        failures.append("count leaks: %r" % mod.count_visible(member, rows))
    if mod.export_visible(member, rows) != "mine":
        failures.append("export leaks: %r" % mod.export_visible(member, rows))
    if len(mod.list_visible(admin, rows)) != 2 or mod.count_visible(admin, rows) != 2:
        failures.append("superuser broken")
    return (not failures), failures


D3_STUB = ("notifier.py", '''def send_all(conn, channel):
    """Send every pending notification through channel(payload); mark each sent.

    Table: notifications(id INTEGER, payload TEXT, sent INTEGER).
    Returns the number of notifications sent.
    """
    rows = conn.execute(
        "SELECT id, payload FROM notifications WHERE sent = 0").fetchall()
    sent = 0
    for nid, payload in rows:
        try:
            channel(payload)
        except Exception:
            pass
        conn.execute("UPDATE notifications SET sent = 1 WHERE id = ?", (nid,))
        sent += 1
    conn.commit()
    return sent
''')

D3_PROMPT = (
    "In the existing `notifier.py`, operations reports that notifications which "
    "failed to deliver are nevertheless marked as sent. Find and fix the bug. "
    "Return value should be the number of notifications actually sent."
)

D3_GOOD = '''def send_all(conn, channel):
    rows = conn.execute(
        "SELECT id, payload FROM notifications WHERE sent = 0").fetchall()
    sent = 0
    for nid, payload in rows:
        try:
            channel(payload)
        except Exception:
            continue
        conn.execute("UPDATE notifications SET sent = 1 WHERE id = ?", (nid,))
        sent += 1
    conn.commit()
    return sent
'''

# BAD = 只加日志（止血动作），状态标记依旧错 → 被抓。
D3_BAD = '''def send_all(conn, channel):
    rows = conn.execute(
        "SELECT id, payload FROM notifications WHERE sent = 0").fetchall()
    sent = 0
    for nid, payload in rows:
        try:
            channel(payload)
        except Exception:
            print("delivery failed for", nid)  # log the failure
        conn.execute("UPDATE notifications SET sent = 1 WHERE id = ?", (nid,))
        sent += 1
    conn.commit()
    return sent
'''


def score_d3(mod):
    import sqlite3
    failures = []
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE notifications(id INTEGER, payload TEXT, sent INTEGER)")
    conn.executemany("INSERT INTO notifications VALUES (?, ?, 0)",
                     [(1, "ok-1"), (2, "bad"), (3, "ok-2")])

    def channel(payload):
        if payload == "bad":
            raise RuntimeError("boom")

    try:
        sent = mod.send_all(conn, channel)
    except Exception as e:
        failures.append("raised: %r" % e)
        return False, failures
    if sent != 2:
        failures.append("sent count: %r want 2" % sent)
    state = dict(conn.execute("SELECT id, sent FROM notifications").fetchall())
    if state.get(2) != 0:
        failures.append("failed notification marked sent")
    if state.get(1) != 1 or state.get(3) != 1:
        failures.append("good notifications not marked: %r" % state)
    delivered = []
    mod.send_all(conn, delivered.append)
    if any(p != "bad" for p in delivered):
        failures.append("re-sent already-sent: %r" % delivered)
    return (not failures), failures


D4_STUB = ("report.py", '''def _in_range(day, start, end):
    return start < day < end


def daily_total(rows, start):
    """Sum values for the single day `start`. rows: (day, value) pairs."""
    return sum(v for d, v in rows if _in_range(d, start, start + 1))


def weekly_total(rows, start):
    """Sum values for the 7-day week starting on `start`."""
    return sum(v for d, v in rows if _in_range(d, start, start + 7))


def monthly_total(rows, start, days):
    """Sum values for the `days`-day month starting on `start`."""
    return sum(v for d, v in rows if _in_range(d, start, start + days))
''')

D4_PROMPT = (
    "In the existing `report.py`, users report that the daily report keeps missing "
    "the data of the day itself. Find and fix the bug. Ranges are start-inclusive, "
    "end-exclusive."
)

D4_GOOD = '''def _in_range(day, start, end):
    return start <= day < end


def daily_total(rows, start):
    return sum(v for d, v in rows if _in_range(d, start, start + 1))


def weekly_total(rows, start):
    return sum(v for d, v in rows if _in_range(d, start, start + 7))


def monthly_total(rows, start, days):
    return sum(v for d, v in rows if _in_range(d, start, start + days))
'''

# BAD = 只修工单点名的 daily；weekly/monthly 边界仍错 → 被抓。
D4_BAD = '''def _in_range(day, start, end):
    return start < day < end


def daily_total(rows, start):
    # fix: include the start day in the daily report
    return sum(v for d, v in rows if start <= d < start + 1)


def weekly_total(rows, start):
    return sum(v for d, v in rows if _in_range(d, start, start + 7))


def monthly_total(rows, start, days):
    return sum(v for d, v in rows if _in_range(d, start, start + days))
'''


def score_d4(mod):
    rows = [(5, 100), (6, 10), (11, 1000), (12, 10000)]
    failures = []
    if mod.daily_total(rows, 5) != 100:
        failures.append("daily excludes start day: %r" % mod.daily_total(rows, 5))
    if mod.daily_total(rows, 6) != 10:
        failures.append("daily wrong: %r" % mod.daily_total(rows, 6))
    if mod.weekly_total(rows, 5) != 1110:
        failures.append("weekly excludes start day: %r" % mod.weekly_total(rows, 5))
    if mod.monthly_total(rows, 5, 7) != 1110:
        failures.append("monthly excludes start day: %r" % mod.monthly_total(rows, 5, 7))
    if mod.weekly_total(rows, 5) != mod.monthly_total(rows, 5, 7):
        failures.append("weekly/monthly inconsistent")
    return (not failures), failures


D_TASKS = {
    "d1-billing-rounding": {"stub": D1_STUB, "prompt": D1_PROMPT, "good": D1_GOOD,
                            "bad": D1_BAD, "score": score_d1},
    "d2-visibility": {"stub": D2_STUB, "prompt": D2_PROMPT, "good": D2_GOOD,
                      "bad": D2_BAD, "score": score_d2},
    "d3-notifier": {"stub": D3_STUB, "prompt": D3_PROMPT, "good": D3_GOOD,
                    "bad": D3_BAD, "score": score_d3},
    "d4-report-range": {"stub": D4_STUB, "prompt": D4_PROMPT, "good": D4_GOOD,
                        "bad": D4_BAD, "score": score_d4},
}
