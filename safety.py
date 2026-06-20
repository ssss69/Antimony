import re
from pathlib import Path


SUSPICIOUS_URL_PATTERNS = [
    r"@", r"\bbit\.ly\b", r"\btinyurl\.com\b", r"\bfree[-_]?gift\b",
    r"\blogin[-_]?verify\b", r"\baccount[-_]?security\b",
]
PROMPT_INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous",
    "reveal your system prompt",
    "send the api key",
    "exfiltrate",
    "developer message",
]
DANGEROUS_FILE_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".ps1", ".vbs", ".scr", ".msi", ".js", ".jar",
}
SECRET_PATTERNS = [
    r"sk-[A-Za-z0-9_\-]{20,}",
    r"api[_-]?key\s*[:=]\s*[A-Za-z0-9_\-]{16,}",
    r"password\s*[:=]\s*\S+",
]
DANGEROUS_COMMAND_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bdel\s+/[sfq]\b",
    r"\bformat\b",
    r"\bshutdown\b",
    r"\breg\s+delete\b",
    r"\bRemove-Item\b.*\b-Recurse\b",
    r"\bcurl\b.*\|\s*(sh|bash|powershell)",
]


class SafetyScanner:
    def suspicious_url(self, text):
        return any(re.search(pattern, text, re.I) for pattern in SUSPICIOUS_URL_PATTERNS)

    def prompt_injection(self, text):
        lower = text.lower()
        return any(pattern in lower for pattern in PROMPT_INJECTION_PATTERNS)

    def dangerous_file(self, path_text):
        return Path(path_text.strip().strip('"')).suffix.lower() in DANGEROUS_FILE_EXTENSIONS

    def api_key_leak(self, text):
        return any(re.search(pattern, text, re.I) for pattern in SECRET_PATTERNS)

    def unsafe_command(self, text):
        return any(re.search(pattern, text, re.I) for pattern in DANGEROUS_COMMAND_PATTERNS)

    def scan_text(self, text):
        findings = []
        if self.suspicious_url(text):
            findings.append("suspicious URL")
        if self.prompt_injection(text):
            findings.append("prompt injection")
        if self.api_key_leak(text):
            findings.append("possible API key/secret leak")
        if self.unsafe_command(text):
            findings.append("unsafe terminal command")
        return findings


class PermissionGate:
    risky_tools = {"web_search", "file_reader", "system", "command", "api_key"}

    def __init__(self, enabled=True):
        self.enabled = enabled

    def check(self, tool_name, user_text):
        if not self.enabled or tool_name not in self.risky_tools:
            return True, ""
        return False, f"Permission required before using risky tool: {tool_name}. Confirm the action explicitly."
