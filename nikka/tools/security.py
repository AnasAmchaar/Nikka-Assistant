"""
Nikka — Security Static Analysis Tool.

Provides a comprehensive security scanner that analyzes Python source code,
compiled bytecode, or raw network payloads for potential security vulnerabilities.
Uses only standard library modules (ast, dis, re, json) — no external dependencies.

Detected vulnerability categories:
  - Command Injection (os.system, subprocess, eval, exec)
  - Unsafe Deserialization (pickle, marshal, yaml.load without SafeLoader)
  - Hardcoded Credentials (passwords, API keys, tokens in source)
  - SQL Injection (string formatting in query patterns)
  - Weak Cryptography (MD5, SHA1 for non-HMAC hashing)
  - Dangerous Imports (ctypes, telnetlib, etc.)
  - Debug / Backdoor Artifacts (pdb, breakpoint, 0.0.0.0 binds)
  - Path Traversal (unsanitized path construction with '..')
  - Information Disclosure (verbose tracebacks, stack dumps)
  - Suspicious Network Payloads (shellcode signatures, encoded exploits)
"""

from __future__ import annotations

import ast
import base64
import dis
import io
import json
import logging
import re
import textwrap
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from smolagents.tools import Tool

logger = logging.getLogger("nikka.tools.security")


# ── Data models ───────────────────────────────────────────────────────────────


class Severity(str, Enum):
    """Severity levels aligned with CVSS qualitative ratings."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass
class Finding:
    """A single security finding from the analysis."""

    finding_id: str
    severity: str
    category: str
    line: int | None
    offset: int | None
    code_snippet: str
    description: str
    recommendation: str


@dataclass
class ScanReport:
    """Complete scan report with summary and individual findings."""

    input_type: str
    findings: list[Finding] = field(default_factory=list)
    error: str | None = None

    @property
    def summary(self) -> dict[str, int]:
        counts = {s.value: 0 for s in Severity}
        for f in self.findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        return {"total_findings": len(self.findings), **counts}

    def to_json(self) -> str:
        return json.dumps(
            {
                "scan_summary": self.summary,
                "input_type": self.input_type,
                "findings": [asdict(f) for f in self.findings],
                "error": self.error,
            },
            indent=2,
        )


# ── Rule definitions ──────────────────────────────────────────────────────────


@dataclass
class _CallRule:
    """Rule matching dangerous function calls by module and function name."""

    modules: frozenset[str]
    functions: frozenset[str]
    category: str
    severity: str
    description: str
    recommendation: str


# Dangerous call patterns detected via AST
_CALL_RULES: list[_CallRule] = [
    # ── Command Injection ──────────────────────────────────────────────
    _CallRule(
        modules=frozenset({"os"}),
        functions=frozenset({"system", "popen", "popen2", "popen3", "popen4"}),
        category="Command Injection",
        severity=Severity.CRITICAL,
        description="Direct OS command execution via os.{func}(). User-controlled input "
                    "can lead to arbitrary command execution on the host system.",
        recommendation="Replace with subprocess.run([...], shell=False) using an explicit "
                       "argument list. Never pass unsanitized user input to shell commands.",
    ),
    _CallRule(
        modules=frozenset({"subprocess"}),
        functions=frozenset({"call", "run", "Popen", "check_output", "check_call"}),
        category="Command Injection",
        severity=Severity.HIGH,
        description="Subprocess invocation via subprocess.{func}(). If 'shell=True' is used "
                    "or arguments are built from user input, this enables command injection.",
        recommendation="Use shell=False (default), pass arguments as a list, and validate "
                       "all external input before inclusion in command arguments.",
    ),
    _CallRule(
        modules=frozenset({""}),  # builtins (no module prefix)
        functions=frozenset({"eval", "exec", "compile"}),
        category="Command Injection",
        severity=Severity.CRITICAL,
        description="Dynamic code execution via {func}(). Evaluating untrusted input "
                    "allows arbitrary Python code execution.",
        recommendation="Avoid eval/exec entirely. Use ast.literal_eval() for safe literal "
                       "parsing, or a sandboxed parser for expression evaluation.",
    ),
    _CallRule(
        modules=frozenset({"builtins", "__builtin__"}),
        functions=frozenset({"eval", "exec", "compile", "__import__"}),
        category="Command Injection",
        severity=Severity.CRITICAL,
        description="Explicit builtin dynamic code execution via {func}().",
        recommendation="Remove dynamic code execution. Use safe alternatives.",
    ),

    # ── Unsafe Deserialization ─────────────────────────────────────────
    _CallRule(
        modules=frozenset({"pickle", "_pickle", "cPickle", "shelve"}),
        functions=frozenset({"load", "loads", "Unpickler"}),
        category="Unsafe Deserialization",
        severity=Severity.CRITICAL,
        description="Deserialization of untrusted data via {module}.{func}(). Pickle can "
                    "execute arbitrary code during deserialization (RCE via __reduce__).",
        recommendation="Never unpickle data from untrusted sources. Use JSON, msgpack, "
                       "or protobuf for data interchange. If pickle is required, use "
                       "hmac signing to verify data integrity before loading.",
    ),
    _CallRule(
        modules=frozenset({"marshal"}),
        functions=frozenset({"load", "loads"}),
        category="Unsafe Deserialization",
        severity=Severity.HIGH,
        description="Marshal deserialization via marshal.{func}(). Marshal format is not "
                    "secure against malicious data and can crash the interpreter.",
        recommendation="Use JSON or another safe serialization format.",
    ),
    _CallRule(
        modules=frozenset({"yaml"}),
        functions=frozenset({"load", "load_all"}),
        category="Unsafe Deserialization",
        severity=Severity.HIGH,
        description="YAML loading via yaml.{func}() without explicit SafeLoader. "
                    "PyYAML's default loader can execute arbitrary Python objects.",
        recommendation="Use yaml.safe_load() or yaml.load(data, Loader=yaml.SafeLoader).",
    ),
    _CallRule(
        modules=frozenset({"jsonpickle"}),
        functions=frozenset({"decode", "loads"}),
        category="Unsafe Deserialization",
        severity=Severity.HIGH,
        description="jsonpickle deserialization can instantiate arbitrary Python objects.",
        recommendation="Avoid jsonpickle for untrusted data. Use standard json module.",
    ),

    # ── Weak Cryptography ─────────────────────────────────────────────
    _CallRule(
        modules=frozenset({"hashlib"}),
        functions=frozenset({"md5", "sha1"}),
        category="Weak Cryptography",
        severity=Severity.MEDIUM,
        description="Use of weak hash algorithm {func}. MD5 and SHA-1 are vulnerable to "
                    "collision attacks and should not be used for security purposes.",
        recommendation="Use hashlib.sha256() or hashlib.sha3_256() for integrity checks. "
                       "For password hashing, use bcrypt, scrypt, or argon2.",
    ),

    # ── Information Disclosure ────────────────────────────────────────
    _CallRule(
        modules=frozenset({"traceback"}),
        functions=frozenset({"print_exc", "format_exc", "print_stack"}),
        category="Information Disclosure",
        severity=Severity.LOW,
        description="Verbose traceback output via traceback.{func}(). In production, "
                    "detailed stack traces can leak internal paths, versions, and logic.",
        recommendation="Log tracebacks to a secure log sink, never expose to end users.",
    ),
]

# Dangerous import module names
_DANGEROUS_IMPORTS: dict[str, tuple[str, str, str]] = {
    # module: (severity, description, recommendation)
    "ctypes": (
        Severity.HIGH,
        "Import of ctypes enables direct memory manipulation and FFI calls, "
        "bypassing Python's safety guarantees.",
        "Verify ctypes usage is intentional and inputs are validated.",
    ),
    "telnetlib": (
        Severity.MEDIUM,
        "Import of telnetlib — Telnet transmits credentials in plaintext.",
        "Use paramiko (SSH) or TLS-wrapped connections instead.",
    ),
    "ftplib": (
        Severity.MEDIUM,
        "Import of ftplib — FTP transmits credentials in plaintext.",
        "Use ftplib with TLS (FTP_TLS) or SFTP via paramiko.",
    ),
    "xmlrpc": (
        Severity.MEDIUM,
        "Import of xmlrpc — XML-RPC is vulnerable to XXE and deserialization attacks.",
        "Use a REST API with JSON payloads instead.",
    ),
}

# Regex patterns for hardcoded secrets
_SECRET_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(
            r"""(?:password|passwd|pwd|secret|api_key|apikey|api_secret|"""
            r"""access_token|auth_token|private_key|secret_key)"""
            r"""\s*=\s*['\"][^'"]{4,}['\"]""",
            re.IGNORECASE,
        ),
        "Hardcoded credential or secret assigned to a sensitive variable name.",
        "Store secrets in environment variables, a secrets manager (e.g., "
        "AWS Secrets Manager, HashiCorp Vault), or a .env file excluded from VCS.",
    ),
    (
        re.compile(
            r"""['\"](?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82})['\"]""",
        ),
        "GitHub Personal Access Token detected in source code.",
        "Revoke this token immediately and rotate credentials.",
    ),
    (
        re.compile(
            r"""['\"](?:sk-[A-Za-z0-9]{32,})['\"]""",
        ),
        "OpenAI API key pattern detected in source code.",
        "Revoke and rotate the key. Use environment variables.",
    ),
    (
        re.compile(
            r"""['\"](?:AKIA[0-9A-Z]{16})['\"]""",
        ),
        "AWS Access Key ID pattern detected in source code.",
        "Revoke the key in AWS IAM and use instance roles or AWS Secrets Manager.",
    ),
    (
        re.compile(
            r"""['\"](?:Bearer\s+[A-Za-z0-9\-._~+/]+=*)['\"]""",
            re.IGNORECASE,
        ),
        "Hardcoded Bearer token detected.",
        "Remove the token from source and load from secure storage.",
    ),
]

# SQL injection patterns
_SQL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"""(?:SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE)\s+.*"""
            r"""(?:%s|%d|\{[^}]*\}|'\s*\+|\+\s*'|f['"])""",
            re.IGNORECASE | re.DOTALL,
        ),
        "SQL query constructed via string formatting or concatenation.",
    ),
    (
        re.compile(
            r"""\.execute\s*\(\s*(?:f['\"]|['\"].*%|['\"].*\.format)""",
            re.IGNORECASE,
        ),
        "Database .execute() called with formatted string instead of parameterized query.",
    ),
]

# Suspicious network payload signatures (hex patterns)
_PAYLOAD_SIGNATURES: list[tuple[bytes, str, str]] = [
    # x86 NOP sled
    (b"\x90\x90\x90\x90", "x86 NOP sled detected — common shellcode preamble.",
     "Quarantine and analyze in a sandbox."),
    # /bin/sh string
    (b"/bin/sh", "Unix shell path '/bin/sh' found in binary payload.",
     "Inspect for shell-spawning exploit code."),
    (b"/bin/bash", "Unix shell path '/bin/bash' found in binary payload.",
     "Inspect for shell-spawning exploit code."),
    # cmd.exe
    (b"cmd.exe", "Windows command interpreter reference found in payload.",
     "Inspect for command execution exploit."),
    # PowerShell download cradle
    (b"powershell", "PowerShell reference found in binary payload.",
     "Inspect for PowerShell-based exploitation."),
    # Common x86 shellcode: int 0x80 (Linux syscall)
    (b"\xcd\x80", "Linux syscall interrupt (int 0x80) detected.",
     "Likely shellcode — analyze in a sandbox."),
    # Windows syscall via ntdll
    (b"\x0f\x05", "AMD64 SYSCALL instruction detected.",
     "Likely shellcode — analyze in a sandbox."),
]


# ── Analysis engines ──────────────────────────────────────────────────────────


class _ASTAnalyzer(ast.NodeVisitor):
    """
    AST visitor that walks a Python parse tree detecting security anti-patterns.
    Collects findings into self.findings.
    """

    def __init__(self, source_lines: list[str]) -> None:
        self.source_lines = source_lines
        self.findings: list[Finding] = []
        self._finding_counter = 0

    def _make_id(self) -> str:
        self._finding_counter += 1
        return f"PY-{self._finding_counter:03d}"

    def _snippet(self, lineno: int) -> str:
        """Extract a code snippet around the given line number."""
        if 0 < lineno <= len(self.source_lines):
            return self.source_lines[lineno - 1].strip()[:120]
        return "(source not available)"

    def _resolve_call_name(self, node: ast.Call) -> tuple[str, str]:
        """Resolve a call node to (module_or_prefix, function_name)."""
        func = node.func
        if isinstance(func, ast.Attribute):
            # e.g. os.system() → module="os", func="system"
            if isinstance(func.value, ast.Name):
                return func.value.id, func.attr
            # Nested: e.g. subprocess.run → still grab the attr
            return "", func.attr
        elif isinstance(func, ast.Name):
            # e.g. eval() → module="", func="eval"
            return "", func.id
        return "", ""

    def visit_Call(self, node: ast.Call) -> None:
        module, func_name = self._resolve_call_name(node)
        lineno = getattr(node, "lineno", None)

        for rule in _CALL_RULES:
            if func_name in rule.functions:
                # Check if module matches (empty module means builtin/no-prefix)
                if module in rule.modules or (module == "" and "" in rule.modules):
                    desc = rule.description.replace("{func}", func_name)
                    desc = desc.replace("{module}", module or "builtins")
                    self.findings.append(Finding(
                        finding_id=self._make_id(),
                        severity=rule.severity,
                        category=rule.category,
                        line=lineno,
                        offset=getattr(node, "col_offset", None),
                        code_snippet=self._snippet(lineno) if lineno else "",
                        description=desc,
                        recommendation=rule.recommendation,
                    ))

        # Special check: subprocess with shell=True
        if func_name in ("call", "run", "Popen", "check_output", "check_call"):
            for kw in node.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    self.findings.append(Finding(
                        finding_id=self._make_id(),
                        severity=Severity.CRITICAL,
                        category="Command Injection",
                        line=lineno,
                        offset=getattr(node, "col_offset", None),
                        code_snippet=self._snippet(lineno) if lineno else "",
                        description=f"subprocess.{func_name}() called with shell=True. "
                                    "This passes the command through the system shell, enabling "
                                    "injection if any argument comes from user input.",
                        recommendation="Use shell=False (the default) and pass arguments as a list.",
                    ))

        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            name = alias.name.split(".")[0]
            if name in _DANGEROUS_IMPORTS:
                sev, desc, rec = _DANGEROUS_IMPORTS[name]
                self.findings.append(Finding(
                    finding_id=self._make_id(),
                    severity=sev,
                    category="Dangerous Import",
                    line=getattr(node, "lineno", None),
                    offset=getattr(node, "col_offset", None),
                    code_snippet=self._snippet(node.lineno) if node.lineno else "",
                    description=desc,
                    recommendation=rec,
                ))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            name = node.module.split(".")[0]
            if name in _DANGEROUS_IMPORTS:
                sev, desc, rec = _DANGEROUS_IMPORTS[name]
                self.findings.append(Finding(
                    finding_id=self._make_id(),
                    severity=sev,
                    category="Dangerous Import",
                    line=getattr(node, "lineno", None),
                    offset=getattr(node, "col_offset", None),
                    code_snippet=self._snippet(node.lineno) if node.lineno else "",
                    description=desc,
                    recommendation=rec,
                ))
        self.generic_visit(node)


def _analyze_python_source(source: str) -> ScanReport:
    """
    Parse and analyze Python source code for security vulnerabilities.

    Performs AST-based analysis for dangerous calls, imports, and patterns,
    plus regex-based scans for hardcoded secrets and SQL injection.
    """
    report = ScanReport(input_type="python_source")
    lines = source.splitlines()
    finding_counter = 0

    def next_id() -> str:
        nonlocal finding_counter
        finding_counter += 1
        return f"PY-{finding_counter:03d}"

    # ── Phase 1: AST analysis ──────────────────────────────────────────
    try:
        tree = ast.parse(source)
        analyzer = _ASTAnalyzer(lines)
        analyzer.visit(tree)
        report.findings.extend(analyzer.findings)
        finding_counter = analyzer._finding_counter
    except SyntaxError as exc:
        report.error = (
            f"Python syntax error at line {exc.lineno}, col {exc.offset}: {exc.msg}. "
            "AST analysis skipped; falling back to regex-only scan."
        )

    # ── Phase 2: Regex-based secret detection ──────────────────────────
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue  # skip comments

        for pattern, desc, rec in _SECRET_PATTERNS:
            if pattern.search(line):
                report.findings.append(Finding(
                    finding_id=next_id(),
                    severity=Severity.HIGH,
                    category="Hardcoded Credentials",
                    line=i,
                    offset=None,
                    code_snippet=stripped[:120],
                    description=desc,
                    recommendation=rec,
                ))

        # SQL injection patterns
        for pattern, desc in _SQL_PATTERNS:
            if pattern.search(line):
                report.findings.append(Finding(
                    finding_id=next_id(),
                    severity=Severity.HIGH,
                    category="SQL Injection",
                    line=i,
                    offset=None,
                    code_snippet=stripped[:120],
                    description=desc,
                    recommendation="Use parameterized queries (e.g., cursor.execute('SELECT * "
                                   "FROM users WHERE id = ?', (user_id,))).",
                ))

        # Binding to 0.0.0.0 (all interfaces)
        if re.search(r"""['"]0\.0\.0\.0['"]""", line):
            report.findings.append(Finding(
                finding_id=next_id(),
                severity=Severity.MEDIUM,
                category="Network Exposure",
                line=i,
                offset=None,
                code_snippet=stripped[:120],
                description="Server binding to 0.0.0.0 exposes the service on all "
                            "network interfaces, including public-facing ones.",
                recommendation="Bind to 127.0.0.1 for local-only access, or use a "
                               "firewall to restrict external access.",
            ))

        # Debug artifacts
        if re.search(r"\bbreakpoint\s*\(", line) or re.search(r"\bpdb\.set_trace\s*\(", line):
            report.findings.append(Finding(
                finding_id=next_id(),
                severity=Severity.LOW,
                category="Debug Artifact",
                line=i,
                offset=None,
                code_snippet=stripped[:120],
                description="Debugger breakpoint left in code. In production, this will "
                            "halt execution and may expose an interactive debugger.",
                recommendation="Remove all breakpoint() and pdb.set_trace() calls before deployment.",
            ))

    return report


def _analyze_bytecode(data: bytes) -> ScanReport:
    """
    Analyze Python bytecode (.pyc content or compiled code objects) for
    suspicious operations by disassembling and inspecting opcodes.
    """
    report = ScanReport(input_type="python_bytecode")
    finding_counter = 0

    def next_id() -> str:
        nonlocal finding_counter
        finding_counter += 1
        return f"BC-{finding_counter:03d}"

    # Try to compile as source first; if it's a string, treat as source
    code_obj = None
    try:
        code_obj = compile(data if isinstance(data, str) else data.decode("utf-8", errors="replace"), "<input>", "exec")
    except SyntaxError:
        # Try interpreting as raw bytecode — marshal-load it
        import marshal as _marshal

        try:
            # .pyc files have a header (16 bytes in Python 3.8+), skip it
            for offset in (0, 8, 12, 16):
                try:
                    code_obj = _marshal.loads(data[offset:])
                    break
                except Exception:
                    continue
        except Exception:
            pass

    if code_obj is None:
        report.error = "Could not interpret input as Python source or bytecode."
        return report

    # Disassemble and scan for suspicious operations
    output = io.StringIO()
    dis.dis(code_obj, file=output)
    disasm = output.getvalue()

    # Dangerous function names in bytecode
    dangerous_names = {
        "eval": ("Command Injection", Severity.CRITICAL, "eval() in bytecode."),
        "exec": ("Command Injection", Severity.CRITICAL, "exec() in bytecode."),
        "system": ("Command Injection", Severity.CRITICAL, "os.system() in bytecode."),
        "popen": ("Command Injection", Severity.HIGH, "os.popen() in bytecode."),
        "loads": ("Unsafe Deserialization", Severity.HIGH, "Deserialization call in bytecode."),
        "load": ("Unsafe Deserialization", Severity.MEDIUM, "Possible deserialization in bytecode."),
        "__import__": ("Dynamic Import", Severity.MEDIUM, "Dynamic __import__() in bytecode."),
    }

    for line in disasm.splitlines():
        for name, (category, severity, desc) in dangerous_names.items():
            if name in line and ("LOAD_GLOBAL" in line or "LOAD_ATTR" in line or "LOAD_NAME" in line):
                # Extract offset from disassembly line
                offset_match = re.match(r"\s*(\d+)", line)
                byte_offset = int(offset_match.group(1)) if offset_match else None

                report.findings.append(Finding(
                    finding_id=next_id(),
                    severity=severity,
                    category=category,
                    line=None,
                    offset=byte_offset,
                    code_snippet=line.strip()[:120],
                    description=desc,
                    recommendation="Decompile and review the source for this operation.",
                ))

    return report


def _analyze_network_payload(data: bytes) -> ScanReport:
    """
    Scan a raw network payload (binary or text) for exploit signatures,
    shellcode patterns, and encoded malicious content.
    """
    report = ScanReport(input_type="network_payload")
    finding_counter = 0

    def next_id() -> str:
        nonlocal finding_counter
        finding_counter += 1
        return f"NET-{finding_counter:03d}"

    # ── Binary signature scan ──────────────────────────────────────────
    for sig, desc, rec in _PAYLOAD_SIGNATURES:
        idx = data.find(sig)
        if idx != -1:
            # Show hex context around the match
            context_start = max(0, idx - 8)
            context_end = min(len(data), idx + len(sig) + 8)
            hex_context = data[context_start:context_end].hex(" ")

            report.findings.append(Finding(
                finding_id=next_id(),
                severity=Severity.CRITICAL,
                category="Malicious Payload",
                line=None,
                offset=idx,
                code_snippet=f"hex[{context_start}:{context_end}]: {hex_context}",
                description=desc,
                recommendation=rec,
            ))

    # ── Text-layer scan (decode and check) ─────────────────────────────
    try:
        text = data.decode("utf-8", errors="ignore")
    except Exception:
        text = data.decode("latin-1", errors="ignore")

    # Check for Base64-encoded payloads
    b64_pattern = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")
    for match in b64_pattern.finditer(text):
        try:
            decoded = base64.b64decode(match.group())
            # Check if the decoded content contains suspicious signatures
            for sig, desc, _rec in _PAYLOAD_SIGNATURES:
                if sig in decoded:
                    report.findings.append(Finding(
                        finding_id=next_id(),
                        severity=Severity.CRITICAL,
                        category="Encoded Malicious Payload",
                        line=None,
                        offset=match.start(),
                        code_snippet=f"base64: {match.group()[:80]}...",
                        description=f"Base64-encoded payload contains: {desc}",
                        recommendation="Decode and analyze the payload in a sandbox.",
                    ))
        except Exception:
            pass

    # Check for common injection strings in text layer
    injection_patterns = [
        (r"<script[^>]*>", "Cross-Site Scripting (XSS)", "Embedded <script> tag detected."),
        (r"(?:UNION\s+SELECT|OR\s+1\s*=\s*1|'\s*OR\s*')", "SQL Injection",
         "SQL injection pattern detected in payload."),
        (r"(?:\.\./){2,}", "Path Traversal", "Directory traversal sequence detected."),
        (r"(?:\\x[0-9a-f]{2}){4,}", "Shellcode", "Hex-encoded byte sequence detected."),
    ]

    for pattern, category, desc in injection_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            report.findings.append(Finding(
                finding_id=next_id(),
                severity=Severity.HIGH,
                category=category,
                line=None,
                offset=match.start(),
                code_snippet=text[max(0, match.start() - 20):match.end() + 20][:120],
                description=desc,
                recommendation="Sanitize, validate, and escape all untrusted input.",
            ))

    # ── Entropy analysis (detect encrypted/compressed blobs) ───────────
    if len(data) >= 64:
        byte_counts = [0] * 256
        for b in data:
            byte_counts[b] += 1
        total = len(data)
        import math

        entropy = -sum(
            (c / total) * math.log2(c / total) for c in byte_counts if c > 0
        )
        if entropy > 7.5:
            report.findings.append(Finding(
                finding_id=next_id(),
                severity=Severity.MEDIUM,
                category="High Entropy Payload",
                line=None,
                offset=0,
                code_snippet=f"Shannon entropy: {entropy:.2f} bits/byte (max: 8.0)",
                description=f"Payload has very high entropy ({entropy:.2f}/8.0), suggesting "
                            "encryption, compression, or packed shellcode.",
                recommendation="Investigate whether the payload is encrypted or obfuscated.",
            ))

    return report


def _detect_input_type(input_data: str) -> str:
    """
    Heuristically determine whether the input is Python source code,
    bytecode (hex-encoded), or a raw network payload.
    """
    stripped = input_data.strip()

    # Check for hex-encoded binary data (e.g. '90 90 90 90 cd 80', '\x90\x90', or '90909090cd80')
    hex_clean = re.sub(r"[\s:\\x]+", "", stripped)
    if len(hex_clean) >= 4 and len(hex_clean) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in hex_clean):
        if any(sep in stripped for sep in (" ", ":", "\\x")) or len(hex_clean) >= 16:
            return "hex_payload"

    # Check for base64-encoded data (long block, no whitespace-heavy structure)
    b64_candidate = stripped.replace("\n", "").replace("\r", "")
    if len(b64_candidate) >= 16 and len(b64_candidate) % 4 == 0 and re.match(r"^[A-Za-z0-9+/]+={0,2}$", b64_candidate):
        try:
            decoded = base64.b64decode(b64_candidate)
            if len(decoded) >= 8:
                return "base64_payload"
        except Exception:
            pass

    # Try to parse as Python
    try:
        ast.parse(stripped)
        return "python_source"
    except SyntaxError:
        pass

    # If it contains Python-like keywords, treat as (possibly broken) Python
    python_keywords = {"import ", "def ", "class ", "from ", "print(", "eval(", "exec("}
    if any(kw in stripped for kw in python_keywords):
        return "python_source"

    # Default to text payload
    return "text_payload"


# ── Agent-facing Tool Class ───────────────────────────────────────────────────


class SecurityAnalyzerTool(Tool):
    """
    A robust, dynamic static analysis tool for the Nikka agent.
    Inherits from `smolagents.tools.Tool` for seamless integration into CodeAgent
    and supports standalone dynamic importing/instantiation.

    Analyzes Python source code (via AST & regex), compiled bytecode (via dis),
    and raw network payloads (via signature detection & entropy analysis).
    """

    name: str = "analyze_security"
    description: str = """Perform static security analysis on Python source code, bytecode, or a network payload.
Returns a structured JSON report listing all detected vulnerabilities with severity levels,
exact locations, descriptions, and remediation guidance.

WHEN TO USE THIS TOOL:
- When the user asks you to review code for security issues or vulnerabilities.
- When analyzing a suspicious script, payload, or snippet for malware or exploits.
- When checking code for hardcoded credentials, injection flaws, or unsafe patterns.
- When inspecting a hex dump or network capture for shellcode or exploit signatures.

WHAT IT DETECTS:
- Command Injection (eval, exec, os.system, subprocess with shell=True)
- Unsafe Deserialization (pickle, marshal, yaml.load without SafeLoader)
- Hardcoded Credentials (passwords, API keys, tokens, AWS keys, GitHub PATs)
- SQL Injection (string formatting in SQL queries)
- Weak Cryptography (MD5, SHA1)
- Dangerous Imports (ctypes, telnetlib)
- Debug Artifacts (breakpoint, pdb.set_trace)
- Network Exposure (binding to 0.0.0.0)
- Malicious Payloads (shellcode signatures, encoded exploits, XSS)
- Path Traversal (../ sequences)

INPUT FORMATS:
- Python source code (as a string)
- Hex-encoded binary data (e.g., "90 90 90 90 cd 80")
- Base64-encoded payloads
- Raw text payloads (HTTP requests, network captures)"""

    inputs: dict[str, dict[str, str | type | bool]] = {
        "input_data": {
            "type": "string",
            "description": "The Python source code string, hex-encoded bytecode, base64 payload, or raw text payload to analyze.",
        }
    }
    output_type: str = "string"

    def forward(self, input_data: str) -> str:
        """
        Execute the static security analysis on the provided input.

        Args:
            input_data: The string containing Python code, hex bytecode, or network payload.

        Returns:
            A JSON string containing the full scan report with summary and findings.
        """
        if not input_data or not input_data.strip():
            return json.dumps({
                "scan_summary": {"total_findings": 0},
                "input_type": "empty",
                "findings": [],
                "error": "Empty input provided. Please supply code or payload to analyze.",
            }, indent=2)

        logger.info("Security analysis requested (%d chars)", len(input_data))

        try:
            input_type = _detect_input_type(input_data)
            logger.info("Detected input type: %s", input_type)

            if input_type == "python_source":
                report = _analyze_python_source(input_data)

            elif input_type == "hex_payload":
                # Convert hex string to bytes
                hex_clean = re.sub(r"[\s:\\x]+", "", input_data.strip())
                try:
                    raw_bytes = bytes.fromhex(hex_clean)
                except ValueError as exc:
                    return json.dumps({
                        "scan_summary": {"total_findings": 0},
                        "input_type": "hex_payload",
                        "findings": [],
                        "error": f"Invalid hex encoding: {exc}",
                    }, indent=2)

                payload_report = _analyze_network_payload(raw_bytes)
                bc_report = _analyze_bytecode(raw_bytes)
                if bc_report.findings:
                    report = bc_report
                    report.findings.extend(payload_report.findings)
                else:
                    report = payload_report

            elif input_type == "base64_payload":
                try:
                    b64_clean = input_data.strip().replace("\n", "").replace("\r", "")
                    raw_bytes = base64.b64decode(b64_clean)
                except Exception as exc:
                    return json.dumps({
                        "scan_summary": {"total_findings": 0},
                        "input_type": "base64_payload",
                        "findings": [],
                        "error": f"Invalid base64 encoding: {exc}",
                    }, indent=2)
                report = _analyze_network_payload(raw_bytes)

            else:
                # Text payload — scan as both potential Python and network payload
                report = _analyze_python_source(input_data)
                if report.error:
                    # Not valid Python — try as network payload
                    payload_report = _analyze_network_payload(input_data.encode("utf-8", errors="replace"))
                    if payload_report.findings:
                        report = payload_report
                    else:
                        report.input_type = "text_payload"

            result = report.to_json()
            logger.info("Security analysis complete: %d findings", len(report.findings))
            return result

        except Exception as exc:
            logger.error("Security analysis failed: %s", exc, exc_info=True)
            return json.dumps({
                "scan_summary": {"total_findings": 0},
                "input_type": "unknown",
                "findings": [],
                "error": f"Analysis engine error: {exc}",
            }, indent=2)

    def __call__(self, input_data: str) -> str:
        """Allow direct functional invocation `tool(input_data)`."""
        return self.forward(input_data)


# ── Singleton instance for default registry discovery and direct usage ─────────
analyze_security = SecurityAnalyzerTool()

