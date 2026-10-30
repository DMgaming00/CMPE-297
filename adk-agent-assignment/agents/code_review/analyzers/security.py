"""AST-based security rules with lightweight intra-function taint tracking.

Taint sources: attributes of a ``request`` object (Flask/Django/FastAPI style) and
``input()``.  Taint propagates through simple assignments inside one function.  This is
deliberately conservative: it finds common, high-signal patterns rather than proving
absence of vulnerabilities.
"""

from __future__ import annotations

import ast
import re

from ..models import Finding
from .ast_utils import (
    call_name,
    dotted_name,
    is_dynamic_string,
    is_false,
    is_true,
    keyword,
    string_text,
)

_SECRET_NAME = re.compile(r"(?i)(passw(or)?d|passwd|pwd|secret|api_?key|access_?key|"
                          r"private_?key|auth_?token|token)$")
_PLACEHOLDER = re.compile(r"(?i)^(|x+|changeme|change-me|your[-_ ].*|<.*>|\*+|example.*|"
                          r"dummy|test|placeholder)$")
_TOKEN_PATTERNS = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{35}"), "Google API key"),
    (re.compile(r"gh[pousr]_[0-9A-Za-z]{36,}"), "GitHub token"),
    (re.compile(r"sk_live_[0-9A-Za-z]{16,}"), "Stripe live secret key"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
]
_SQL = re.compile(r"(?i)\b(select|insert|update|delete|drop|create|alter)\b")
_SUBPROCESS = {"subprocess.run", "subprocess.call", "subprocess.Popen", "subprocess.check_call",
               "subprocess.check_output"}
_HTTP_SINKS = {"requests.get", "requests.post", "requests.put", "requests.delete",
               "requests.request", "httpx.get", "httpx.post", "urllib.request.urlopen",
               "urlopen"}
_FILE_SINKS = {"open", "send_file", "flask.send_file", "os.remove", "shutil.rmtree"}
_DESERIALIZE = {"pickle.loads", "pickle.load", "cPickle.loads", "marshal.loads", "dill.loads",
                "dill.load", "jsonpickle.decode"}
_TLS_CALLS = ("requests.", "httpx.", "session.", "client.")


def _is_tainted(node: ast.AST, tainted: set[str]) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id in tainted:
            return True
        if isinstance(sub, ast.Attribute) and dotted_name(sub).startswith("request."):
            return True
        if isinstance(sub, ast.Call) and call_name(sub) == "input":
            return True
    return False


class _SecurityVisitor(ast.NodeVisitor):
    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.findings: list[Finding] = []
        self.tainted: set[str] = set()
        self.sql_strings: set[str] = set()

    def add(self, node: ast.AST, rule: str, severity: str, title: str, explanation: str,
            recommendation: str, confidence: str = "high") -> None:
        self.findings.append(Finding(
            rule_id=rule, title=title, severity=severity, category="security",
            file=self.filename, line=getattr(node, "lineno", 1),
            end_line=getattr(node, "end_lineno", None), explanation=explanation,
            recommendation=recommendation, confidence=confidence))

    # -- scope handling -------------------------------------------------------------
    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        saved = (self.tainted, self.sql_strings)
        self.tainted, self.sql_strings = set(), set()
        self.generic_visit(node)
        self.tainted, self.sql_strings = saved

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Assign(self, node: ast.Assign) -> None:
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if _is_tainted(node.value, self.tainted):
            self.tainted.update(names)
        if is_dynamic_string(node.value) and _SQL.search(string_text(node.value)):
            self.sql_strings.update(names)
        self._check_secret_assignment(node.targets, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self._check_secret_assignment([node.target], node.value)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            for pattern, label in _TOKEN_PATTERNS:
                if pattern.search(node.value):
                    self.add(node, "SEC006", "P0", f"Hard-coded {label}",
                             f"A literal that looks like a real {label} is committed in "
                             "source code; anyone with repository access can use it.",
                             "Revoke/rotate the credential now, then load it from a secret "
                             "manager or environment variable.")
                    break

    # -- sinks ------------------------------------------------------------------------
    def visit_Call(self, node: ast.Call) -> None:
        name = call_name(node)
        first = node.args[0] if node.args else None
        self._check_code_exec(node, name, first)
        self._check_command(node, name, first)
        self._check_sql(node, name, first)
        self._check_deserialization(node, name)
        self._check_tls_and_debug(node, name)
        self._check_crypto(node, name)
        self._check_untrusted_sinks(node, name)
        for kw in node.keywords:
            if kw.arg and _SECRET_NAME.search(kw.arg) and isinstance(kw.value, ast.Constant) \
                    and isinstance(kw.value.value, str) \
                    and not _PLACEHOLDER.match(kw.value.value) and len(kw.value.value) >= 6:
                self.add(kw.value, "SEC006", "P1", f"Hard-coded credential passed as '{kw.arg}'",
                         "Credentials in source code leak through version control and logs.",
                         "Read the value from configuration/secret storage at runtime.")
        self.generic_visit(node)

    def _check_code_exec(self, node: ast.Call, name: str, first: ast.expr | None) -> None:
        if name not in {"eval", "exec"} or first is None:
            return
        if isinstance(first, ast.Constant):
            self.add(node, "SEC001", "P2", f"Use of {name}() on a literal",
                     f"{name}() is unnecessary for constant code and invites future misuse.",
                     "Replace with direct code or ast.literal_eval for literals.", "medium")
        else:
            tainted = _is_tainted(first, self.tainted)
            self.add(node, "SEC001", "P0", f"{name}() on dynamic input",
                     f"{name}() executes arbitrary Python. "
                     + ("The argument is derived from user input: remote code execution."
                        if tainted else "If the value is ever attacker-influenced this is RCE."),
                     "Remove eval/exec. Parse data with json/ast.literal_eval or dispatch "
                     "through an explicit allow-list of operations.",
                     "high" if tainted else "medium")

    def _check_command(self, node: ast.Call, name: str, first: ast.expr | None) -> None:
        if name in _SUBPROCESS and is_true(keyword(node, "shell")):
            dynamic = first is not None and (is_dynamic_string(first)
                                             or _is_tainted(first, self.tainted)
                                             or isinstance(first, ast.Name))
            self.add(node, "SEC002", "P0" if dynamic else "P1",
                     "Shell command injection risk (shell=True)",
                     "shell=True passes the command to /bin/sh; "
                     + ("the command string is built dynamically, so metacharacters in the "
                        "input (; | $()) run arbitrary commands." if dynamic else
                        "any future interpolation becomes command injection."),
                     "Pass an argument list without shell=True, e.g. "
                     "subprocess.run(['ping', '-c', '1', host], check=True, timeout=10); "
                     "validate inputs against an allow-list.")
        elif name in {"os.system", "os.popen"} and first is not None \
                and not isinstance(first, ast.Constant):
            self.add(node, "SEC002", "P0", f"Command injection via {name}()",
                     f"{name}() runs its argument through the shell; the argument is dynamic.",
                     "Use subprocess.run([...]) with an argument list and no shell.")

    def _check_sql(self, node: ast.Call, name: str, first: ast.expr | None) -> None:
        if not isinstance(node.func, ast.Attribute) or first is None:
            return
        if node.func.attr not in {"execute", "executemany", "executescript", "raw"}:
            return
        formatted = is_dynamic_string(first) and bool(_SQL.search(string_text(first)))
        via_variable = isinstance(first, ast.Name) and first.id in self.sql_strings
        if formatted or via_variable:
            self.add(node, "SEC003", "P0", "SQL injection: query built with string formatting",
                     "User-controlled values interpolated into SQL can change the query "
                     "(e.g. ' OR '1'='1), exposing or destroying data.",
                     "Use parameterised queries: cursor.execute('SELECT ... WHERE id = ?', "
                     "(user_id,)). Never format SQL strings.")

    def _check_deserialization(self, node: ast.Call, name: str) -> None:
        if name in _DESERIALIZE:
            self.add(node, "SEC004", "P1", f"Unsafe deserialization with {name}()",
                     "Unpickling attacker-controlled bytes executes arbitrary code.",
                     "Use a data-only format (JSON) or sign and verify payloads (hmac) "
                     "before deserializing.")
        if name == "yaml.unsafe_load" or (name == "yaml.load" and not self._safe_yaml(node)):
            self.add(node, "SEC005", "P1", "yaml.load without SafeLoader",
                     "yaml.load with the default/full loader can construct arbitrary objects.",
                     "Use yaml.safe_load(data).")

    @staticmethod
    def _safe_yaml(node: ast.Call) -> bool:
        loader = keyword(node, "Loader") or (node.args[1] if len(node.args) > 1 else None)
        return loader is not None and "Safe" in dotted_name(loader)

    def _check_tls_and_debug(self, node: ast.Call, name: str) -> None:
        if is_false(keyword(node, "verify")) and (name.startswith(_TLS_CALLS)
                                                  or name in _HTTP_SINKS):
            self.add(node, "SEC007", "P1", "TLS certificate verification disabled",
                     "verify=False allows man-in-the-middle interception of the connection.",
                     "Remove verify=False; if needed, pass a CA bundle path instead.")
        if name.endswith(".run") and is_true(keyword(node, "debug")):
            self.add(node, "SEC010", "P1", "Debug mode enabled in app.run()",
                     "Flask/Werkzeug debug mode exposes an interactive console (remote code "
                     "execution) and stack traces.",
                     "Drive debug from configuration and keep it off in production.")

    def _check_crypto(self, node: ast.Call, name: str) -> None:
        weak = name in {"hashlib.md5", "hashlib.sha1"} or (
            name == "hashlib.new" and node.args and isinstance(node.args[0], ast.Constant)
            and str(node.args[0].value).lower() in {"md5", "sha1"})
        if weak:
            password = any("pass" in n.lower() for n in _identifiers(node))
            self.add(node, "SEC008", "P1" if password else "P2",
                     "Weak hash algorithm" + (" for passwords" if password else ""),
                     "MD5/SHA-1 are broken for collision resistance and far too fast for "
                     "password storage.",
                     "Use hashlib.sha256 for integrity; use bcrypt/scrypt/argon2 "
                     "(or hashlib.scrypt) for passwords.")
        if name == "tempfile.mktemp":
            self.add(node, "SEC009", "P2", "Insecure temporary file (tempfile.mktemp)",
                     "mktemp returns a predictable name that another process can create first.",
                     "Use tempfile.NamedTemporaryFile() or tempfile.mkstemp().")

    def _check_untrusted_sinks(self, node: ast.Call, name: str) -> None:
        args = list(node.args) + [kw.value for kw in node.keywords]
        if not any(_is_tainted(a, self.tainted) for a in args):
            return
        if name in _FILE_SINKS or name.endswith(".send_file"):
            self.add(node, "SEC012", "P1", "Path traversal: file path from user input",
                     "A request-controlled path such as ../../etc/passwd can read or delete "
                     "files outside the intended directory.",
                     "Resolve the path and verify it stays under an allowed base directory "
                     "(Path(base, name).resolve().is_relative_to(base)), or use "
                     "send_from_directory with a sanitised file name.")
        elif name in _HTTP_SINKS:
            self.add(node, "SEC013", "P1", "Server-side request forgery (SSRF)",
                     "The server fetches a URL chosen by the user, enabling access to "
                     "internal services and cloud metadata endpoints.",
                     "Allow-list destination hosts/schemes, block private/link-local IPs and "
                     "disable redirects to untrusted hosts.")

    def _check_secret_assignment(self, targets: list[ast.expr], value: ast.expr) -> None:
        if not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
            return
        if _PLACEHOLDER.match(value.value) or len(value.value) < 6:
            return
        for target in targets:
            name = target.id if isinstance(target, ast.Name) else (
                target.attr if isinstance(target, ast.Attribute) else "")
            if name and _SECRET_NAME.search(name):
                self.add(value, "SEC006", "P1", f"Hard-coded secret in '{name}'",
                         "Secrets committed to source control are effectively public and "
                         "cannot be rotated without a code change.",
                         f"Load {name} from an environment variable or secret manager.")


def _identifiers(node: ast.AST) -> list[str]:
    names = [n.id for n in ast.walk(node) if isinstance(n, ast.Name)]
    names += [n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)]
    return names


def check_security(tree: ast.AST, filename: str) -> list[Finding]:
    visitor = _SecurityVisitor(filename)
    visitor.visit(tree)
    return visitor.findings
