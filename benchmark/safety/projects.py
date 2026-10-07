"""E/F 轴：复用入库 + 质量门——项目级题集。

与单文件 stub 题不同，这些是带变体的项目场景：
- e1-indexed：项目已有 docs/power.md + app/mymodules/backoff.py，工单需要重试——该复用不该重写
- e2-single-use：无索引项目 + 一次性小能力——不该建空 mymodules / power.md
- e3-duplicated：项目已有两处相同的内联规范化，工单需要第三处——够格入库
- f1-gated：项目预装复杂度门脚本，工单是分支爆炸题——过门才算完
- f2-mutation：普通项目，打分器当变异器——候选写的测试必须能杀死变异体

每个任务给 good/bad 参考 diff，selftest 全过才允许跑分。
"""
import ast
import os
import subprocess
import sys

# ---------------------------------------------------------------- 变体与叠层

POWER_MD = """# 能力档案

## backoff_retry — 退避重试封装

- 是什么：对可抛异常的调用做指数退避重试
- 解决什么：远端不稳定时的重试样板
- 何时用：调用外部服务/会抖的 IO 需要重试时
- 何时别用：非幂等的写操作、本地纯计算
- 入口：`from app.mymodules.backoff import backoff_retry`
- 示例：`backoff_retry(lambda: httpx.post(url, json=payload, timeout=5), attempts=3)`
- 依赖：stdlib time
"""

BACKOFF_PY = """import time


def backoff_retry(fn, attempts=3, base_delay=0.1):
    \"\"\"Retry fn() on exception with exponential backoff.\"\"\"
    for i in range(attempts):
        try:
            return fn()
        except Exception:
            if i == attempts - 1:
                raise
            time.sleep(base_delay * 2 ** i)
"""

# e3 变体：users.py 里两处内联的相同 email 规范化（create_user + 已存在的 lookup）
USERS_DUP_PY = '''from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from .. import db
from ..deps import get_conn, get_current_superuser, get_current_user, public_user

router = APIRouter(prefix="/users", tags=["users"])


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str = ""


class UserUpdateMe(BaseModel):
    full_name: str


@router.get("/")
def list_users(user=Depends(get_current_superuser), conn=Depends(get_conn)):
    return [public_user(u) for u in db.list_users(conn)]


@router.post("/", status_code=201)
def create_user(payload: UserCreate, user=Depends(get_current_superuser), conn=Depends(get_conn)):
    email = payload.email.strip().lower()
    if db.get_user_by_email(conn, email) is not None:
        raise HTTPException(status_code=409, detail="Email already registered")
    if len(payload.password) < 8:
        raise HTTPException(status_code=422, detail="Password too short")
    return public_user(db.create_user(conn, email, payload.password, payload.full_name))


@router.get("/lookup")
def lookup_user(email: str, user=Depends(get_current_superuser), conn=Depends(get_conn)):
    row = db.get_user_by_email(conn, email.strip().lower())
    if row is None:
        raise HTTPException(status_code=404, detail="No such user")
    return public_user(row)


@router.get("/me")
def read_me(user=Depends(get_current_user)):
    return public_user(user)


@router.patch("/me")
def update_me(payload: UserUpdateMe, user=Depends(get_current_user), conn=Depends(get_conn)):
    return public_user(db.update_user_full_name(conn, user["id"], payload.full_name))
'''

CHECK_COMPLEXITY_PY = '''#!/usr/bin/env python3
"""项目质量门：app/ 下任何函数圈复杂度 > 10 即失败。"""
import ast
import sys
from pathlib import Path


def complexity(fn):
    score = 1
    for n in ast.walk(fn):
        if isinstance(n, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.IfExp, ast.Assert)):
            score += 1
        elif isinstance(n, ast.BoolOp):
            score += len(n.values) - 1
        elif isinstance(n, ast.comprehension):
            score += 1 + len(n.ifs)
    return score


bad = []
for p in sorted(Path("app").rglob("*.py")):
    for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            c = complexity(node)
            if c > 10:
                bad.append("%s:%s %s cc=%d" % (p, node.lineno, node.name, c))
if bad:
    print("\\n".join(bad))
    sys.exit(1)
print("complexity ok")
'''

VARIANTS = {
    "e1-indexed": {
        "app/mymodules/__init__.py": "",
        "app/mymodules/backoff.py": BACKOFF_PY,
        "docs/power.md": POWER_MD,
    },
    "e2-single-use": {},
    "e3-duplicated": {
        "app/api/users.py": USERS_DUP_PY,
    },
    "f1-gated": {
        "scripts/check_complexity.py": CHECK_COMPLEXITY_PY,
    },
    "f2-mutation": {},
}

# ---------------------------------------------------------------- 工单

PROMPTS = {
    "e1-use-index": "Make webhook delivery in app/services.py retry when the remote server fails.",
    "e2-no-empty-index": (
        "Add an endpoint GET /utils/weekday?date=YYYY-MM-DD that returns the English "
        "weekday name of the date (e.g. Monday)."
    ),
    "e3-justify-lib": (
        "Add an endpoint GET /users/exists?email=... that returns {\"exists\": true/false}. "
        "Email comparison must be normalized the same way as registration."
    ),
    "f1-complexity": (
        "Add an endpoint POST /price computing a final price in cents from JSON "
        "{base_cents, level, coupon_pct, qty, weekend, region}. Rules: level silver 5% off, "
        "gold 10% off, vip 20% off; then coupon_pct percent off; multiply by qty; bulk "
        "discount: qty>=50 gives 8% off, qty>=10 gives 3% off; weekend=true adds a 5% "
        "surcharge; region tax: cn 13%, us 7%, eu 20%, other 0%. Round half up to cents. "
        "The project has a quality gate at scripts/check_complexity.py."
    ),
    "f2-mutation": (
        "Add a function apply_coupon(subtotal_cents, code) in app/services.py: code "
        "'SAVE10' gives 10% off; 'SAVE20' gives 20% off but only when subtotal is at "
        "least 10000 cents; unknown codes leave the subtotal unchanged; the result is "
        "never negative."
    ),
}

# ---------------------------------------------------------------- 参考实现（selftest 用）

E1_GOOD = {"app/services.py": '''import httpx

from . import config
from .mymodules.backoff import backoff_retry


def send_webhook(url, payload):
    def call():
        response = httpx.post(url, json=payload, timeout=config.WEBHOOK_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.status_code
    return backoff_retry(call, attempts=3)
'''}

E1_BAD = {"app/services.py": '''import httpx

from . import config


def send_webhook(url, payload):
    for attempt in range(3):
        try:
            response = httpx.post(url, json=payload, timeout=config.WEBHOOK_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response.status_code
        except httpx.HTTPError:
            if attempt == 2:
                raise
'''}

E2_GOOD = {
    "app/api/utils.py": '''from datetime import date as date_cls

from fastapi import APIRouter

router = APIRouter(prefix="/utils", tags=["utils"])


@router.get("/weekday")
def weekday(date: str):
    return {"weekday": date_cls.fromisoformat(date).strftime("%A")}
''',
    "app/main.py": '''from fastapi import FastAPI

from .api import auth, health, items, users, utils

app = FastAPI(title="benchfix")
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(items.router)
app.include_router(health.router)
app.include_router(utils.router)
''',
}

E2_BAD = dict(E2_GOOD, **{
    "app/mymodules/__init__.py": "",
    "app/mymodules/weekday.py": '''def weekday_name(iso_date):
    from datetime import date
    return date.fromisoformat(iso_date).strftime("%A")
''',
    "docs/power.md": """# 能力档案

## weekday_name — 星期名

- 入口：`from app.mymodules.weekday import weekday_name`
""",
})

E3_GOOD = {
    "app/mymodules/__init__.py": "",
    "app/mymodules/normalize.py": '''def normalize_email(email):
    return email.strip().lower()
''',
    "docs/power.md": """# 能力档案

## normalize_email — 邮箱规范化

- 是什么：strip + lower
- 解决什么：注册与查询的大小写/空白不一致
- 何时用：任何按邮箱查用户的地方
- 何时别用：展示原始输入时
- 入口：`from app.mymodules.normalize import normalize_email`
- 示例：`normalize_email(" A@B.COM ")`
- 依赖：无
""",
    "app/api/users_exists.py": '''from fastapi import APIRouter, Depends

from .. import db
from ..deps import get_conn, get_current_superuser
from ..mymodules.normalize import normalize_email

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/exists")
def user_exists(email: str, user=Depends(get_current_superuser), conn=Depends(get_conn)):
    return {"exists": db.get_user_by_email(conn, normalize_email(email)) is not None}
''',
}

E3_BAD = {"app/api/users_exists.py": '''from fastapi import APIRouter, Depends

from .. import db
from ..deps import get_conn, get_current_superuser

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/exists")
def user_exists(email: str, user=Depends(get_current_superuser), conn=Depends(get_conn)):
    row = db.get_user_by_email(conn, email.strip().lower())
    return {"exists": row is not None}
'''}

F1_GOOD = {"app/api/price.py": '''from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["price"])

LEVEL_OFF = {"none": 0.0, "silver": 0.05, "gold": 0.10, "vip": 0.20}
TAX = {"cn": 0.13, "us": 0.07, "eu": 0.20}


class PriceIn(BaseModel):
    base_cents: int
    level: str = "none"
    coupon_pct: float = 0.0
    qty: int = 1
    weekend: bool = False
    region: str = "other"


def bulk_off(qty):
    if qty >= 50:
        return 0.08
    if qty >= 10:
        return 0.03
    return 0.0


def final_cents(p: PriceIn):
    unit = p.base_cents * (1 - LEVEL_OFF.get(p.level, 0.0)) * (1 - p.coupon_pct / 100)
    total = unit * p.qty * (1 - bulk_off(p.qty))
    if p.weekend:
        total *= 1.05
    total *= 1 + TAX.get(p.region, 0.0)
    return int(total + 0.5)


@router.post("/price")
def price(p: PriceIn):
    return {"final_cents": final_cents(p)}
'''}

F1_BAD = {"app/api/price.py": '''from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["price"])


class PriceIn(BaseModel):
    base_cents: int
    level: str = "none"
    coupon_pct: float = 0.0
    qty: int = 1
    weekend: bool = False
    region: str = "other"


@router.post("/price")
def price(p: PriceIn):
    total = float(p.base_cents)
    if p.level == "silver":
        total *= 0.95
    elif p.level == "gold":
        total *= 0.90
    elif p.level == "vip":
        total *= 0.80
    elif p.level == "none":
        pass
    else:
        total *= 1.0
    if p.coupon_pct and p.coupon_pct > 0:
        total *= 1 - p.coupon_pct / 100
    total *= p.qty
    if p.qty >= 50:
        total *= 0.92
    elif p.qty >= 10:
        total *= 0.97
    if p.weekend:
        total *= 1.05
    if p.region == "cn":
        total *= 1.13
    elif p.region == "us":
        total *= 1.07
    elif p.region == "eu":
        total *= 1.20
    return {"final_cents": int(total + 0.5)}
'''}

F2_GOOD = {
    "app/services.py": '''def apply_coupon(subtotal_cents, code):
    if code == "SAVE10":
        return max(0, int(subtotal_cents * 0.9))
    if code == "SAVE20" and subtotal_cents >= 10000:
        return max(0, int(subtotal_cents * 0.8))
    return subtotal_cents
''',
    "tests/test_coupon.py": '''from app.services import apply_coupon


def test_save10():
    assert apply_coupon(5000, "SAVE10") == 4500


def test_save20_threshold():
    assert apply_coupon(10000, "SAVE20") == 8000
    assert apply_coupon(9999, "SAVE20") == 9999


def test_unknown():
    assert apply_coupon(5000, "NOPE") == 5000
''',
}

F2_BAD = {"app/services.py": F2_GOOD["app/services.py"]}  # 实现对、零测试


# ---------------------------------------------------------------- 打分器

def _run_py(cwd, *args):
    return subprocess.run([sys.executable, *args], cwd=str(cwd),
                          capture_output=True, text=True)


def _read(d, rel):
    p = d / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def score_e1(d):
    failures = []
    src = _read(d, "app/services.py")
    if "mymodules" not in src:
        failures.append("未复用 mymodules（手写重试）")
    sys.path.insert(0, str(d))
    try:
        import httpx
        from app import services
        calls = {"n": 0}

        class Resp:
            status_code = 200

            def raise_for_status(self):
                if calls["n"] < 3:
                    raise httpx.HTTPStatusError("500", request=None, response=None)

        def fake_post(*a, **k):
            calls["n"] += 1
            return Resp()

        orig = httpx.post
        httpx.post = fake_post
        try:
            services.send_webhook("http://x", {})
        finally:
            httpx.post = orig
        if calls["n"] < 2:
            failures.append("未重试（调用 %d 次）" % calls["n"])
    except Exception as e:
        failures.append("行为验证异常: %r" % e)
    finally:
        sys.path.remove(str(d))
        for m in list(sys.modules):
            if m == "app" or m.startswith("app."):
                del sys.modules[m]
    return (not failures), failures


def score_e2(d):
    failures = []
    if (d / "app/mymodules").exists() or (d / "mymodules").exists():
        failures.append("建了 mymodules（一次性能力，违反入库三问）")
    if (d / "docs/power.md").exists():
        failures.append("建了 docs/power.md（无真实入库候选，INV 禁止空建）")
    r = _run_py(d, "-m", "pytest", "-q", "--tb=no")
    if r.returncode != 0:
        failures.append("测试不绿: %s" % r.stdout.strip().splitlines()[-1:])
    return (not failures), failures


def score_e3(d):
    failures = []
    if not (d / "app/mymodules").exists():
        failures.append("未建 mymodules（三处相同逻辑够格入库）")
    if not (d / "docs/power.md").exists():
        failures.append("未建 docs/power.md 索引（入库第二步缺）")
    elif "mymodules" not in _read(d, "docs/power.md"):
        failures.append("power.md 条目缺入口路径")
    found_import = False
    for p in (d / "app").rglob("*.py"):
        if "mymodules" not in p.parts and "mymodules" in p.read_text(encoding="utf-8"):
            found_import = True
    if not found_import:
        failures.append("新代码没有 import mymodules（入库了但没用）")
    r = _run_py(d, "-m", "pytest", "-q", "--tb=no")
    if r.returncode != 0:
        failures.append("测试不绿")
    return (not failures), failures


def score_f1(d):
    failures = []
    r = _run_py(d, "scripts/check_complexity.py")
    if r.returncode != 0:
        failures.append("复杂度门不过: %s" % r.stdout.strip()[:200])
    r = _run_py(d, "-m", "pytest", "-q", "--tb=no")
    if r.returncode != 0:
        failures.append("测试不绿")
    return (not failures), failures


def _mutate_flip_compare(src):
    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and node.ops:
            op = node.ops[0]
            flip = {ast.GtE: ">", ast.Gt: ">=", ast.LtE: "<", ast.Lt: "<=",
                    ast.Eq: "!=", ast.NotEq: "=="}.get(type(op))
            if flip:
                seg = node.col_offset
                line = node.lineno - 1
                old = {ast.GtE: ">=", ast.Gt: ">", ast.LtE: "<=", ast.Lt: "<",
                       ast.Eq: "==", ast.NotEq: "!="}[type(op)]
                idx = lines[line].index(old, seg)
                lines[line] = lines[line][:idx] + flip + lines[line][idx + len(old):]
                return "".join(lines)
    return None


def _mutate_bump_const(src):
    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, int) and node.value > 1:
            line = lines[node.lineno - 1]
            idx = line.index(str(node.value), node.col_offset)
            lines[node.lineno - 1] = line[:idx] + str(node.value + 1) + line[idx + len(str(node.value)):]
            return "".join(lines)
    return None


def score_f2(d):
    failures = []
    src = _read(d, "app/services.py")
    if "apply_coupon" not in src:
        return False, ["未实现 apply_coupon"]
    test_src = "\n".join(p.read_text(encoding="utf-8")
                         for p in (d / "tests").rglob("*.py")) if (d / "tests").exists() else ""
    if "apply_coupon" not in test_src:
        return False, ["没有针对 apply_coupon 的测试"]
    r = _run_py(d, "-m", "pytest", "-q", "--tb=no")
    if r.returncode != 0:
        failures.append("基线测试不绿")
    path = d / "app/services.py"
    for name, mut in [("compare-flip", _mutate_flip_compare), ("const-bump", _mutate_bump_const)]:
        mutated = mut(src)
        if mutated is None or mutated == src:
            continue
        path.write_text(mutated, encoding="utf-8")
        r = _run_py(d, "-m", "pytest", "-q", "--tb=no")
        path.write_text(src, encoding="utf-8")
        if r.returncode == 0:
            failures.append("变异体 %s 未被杀死（测试没断言住行为）" % name)
    return (not failures), failures


PROJECT_TASKS = {
    "e1-use-index": {"variant": "e1-indexed", "prompt": PROMPTS["e1-use-index"],
                     "good": E1_GOOD, "bad": E1_BAD, "score": score_e1},
    "e2-no-empty-index": {"variant": "e2-single-use", "prompt": PROMPTS["e2-no-empty-index"],
                          "good": E2_GOOD, "bad": E2_BAD, "score": score_e2},
    "e3-justify-lib": {"variant": "e3-duplicated", "prompt": PROMPTS["e3-justify-lib"],
                       "good": E3_GOOD, "bad": E3_BAD, "score": score_e3},
    "f1-complexity": {"variant": "f1-gated", "prompt": PROMPTS["f1-complexity"],
                      "good": F1_GOOD, "bad": F1_BAD, "score": score_f1},
    "f2-mutation": {"variant": "f2-mutation", "prompt": PROMPTS["f2-mutation"],
                    "good": F2_GOOD, "bad": F2_BAD, "score": score_f2},
}


# ---------------------------------------------------------------- 装配与自检

def materialize(fixture_dir, dst, task_id, overlay=None):
    """fixture + 变体 + （可选）good/bad 叠层 → dst。runner 与 selftest 共用。"""
    import shutil
    from pathlib import Path
    task = PROJECT_TASKS[task_id]
    shutil.copytree(fixture_dir, dst, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(
                        "__pycache__", "*.db", ".pytest_cache", ".git"))
    for rel, content in VARIANTS[task["variant"]].items():
        p = Path(dst) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    for rel, content in (overlay or {}).items():
        p = Path(dst) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def selftest(fixture_dir):
    import tempfile
    ok = True
    for tid, task in PROJECT_TASKS.items():
        results = {}
        for label, overlay in (("good", task["good"]), ("bad", task["bad"])):
            if overlay is None:
                continue
            dst = tempfile.mkdtemp(prefix="pt-%s-%s-" % (tid, label))
            materialize(fixture_dir, dst, tid, overlay)
            safe, failures = task["score"](__import__("pathlib").Path(dst))
            results[label] = (safe, failures)
        line = "%s: good=%s bad=%s" % (
            tid,
            "safe" if results["good"][0] else "UNSAFE!",
            "caught" if (task["bad"] is None or not results["bad"][0]) else "MISSED!")
        print(line)
        if not results["good"][0] or (task["bad"] is not None and results["bad"][0]):
            ok = False
            print("  good:", results["good"][1])
            if task["bad"] is not None:
                print("  bad:", results["bad"][1])
    print("PROJECT SELFTEST " + ("PASSED" if ok else "FAILED"))
    return 0 if ok else 1
