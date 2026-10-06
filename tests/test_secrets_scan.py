"""Fake secrets are assembled at runtime so this file never contains one literally."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_project.secrets_scan import ALLOW_PRAGMA, is_env_file, scan

FAKE_AWS = "AKIA" + "ABCDEFGHIJKLMNOP"
FAKE_PASSWORD = "S3cr" + "etValue!42"
PEM_HEADER = "-----BEGIN " + "RSA PRIVATE KEY-----"


def write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.mark.parametrize(
    ("rel", "content", "kind"),
    [
        ("app/settings.py", f'DB_PASSWORD = "{FAKE_PASSWORD}"\n', "hard-coded"),
        ("config.yaml", f"api_key: {FAKE_PASSWORD}\n", "hard-coded"),
        ("app/conf.py", f'password: str = "{FAKE_PASSWORD}"\n', "hard-coded"),
        ("notes.md", f"key {FAKE_AWS}\n", "AWS access key"),
        ("deploy/key.txt", PEM_HEADER + "\n", "private key"),
        (
            "app/db.py",
            f'URL = "postgres://admin:{FAKE_PASSWORD}@db:5432/app"\n',
            "credentials in URL",
        ),
    ],
)
def test_detects_secrets(tmp_path: Path, rel: str, content: str, kind: str) -> None:
    write(tmp_path, rel, content)
    findings = scan(tmp_path)
    assert len(findings) == 1
    assert kind in findings[0].kind
    assert findings[0].line == 1


@pytest.mark.parametrize(
    "content",
    [
        'password = os.environ["DB_PASSWORD"]\n',
        "password: str\n",
        "env_secrets: list[Finding]\n",
        "api_token: Optional[str] = None\n",
        'API_KEY = "<injected-at-runtime>"\n',
        "token = settings.auth.token\n",
        'SECRET_KEY = "changeme-in-prod"\n',
        "password = get_password()\n",
        'token_url = "https://idp.example.org/token"\n',
        f'TEST_PW = "{FAKE_PASSWORD}"  # {ALLOW_PRAGMA}\n',
    ],
)
def test_ignores_placeholders_and_code(tmp_path: Path, content: str) -> None:
    write(tmp_path, "app/config.py", content)
    assert scan(tmp_path) == []


def test_env_files_are_flagged_separately(tmp_path: Path) -> None:
    write(tmp_path, ".env", f"DB_PASSWORD={FAKE_PASSWORD}\nLOG_LEVEL=INFO\n")
    write(tmp_path, ".env.example", "DB_PASSWORD=<injected-at-runtime>\n")
    findings = scan(tmp_path)
    assert [(f.path, f.in_env_file) for f in findings] == [(".env", True)]


def test_skips_vendor_dirs_kit_knowledge_and_binaries(tmp_path: Path) -> None:
    write(tmp_path, "node_modules/lib/x.js", f'password = "{FAKE_PASSWORD}"\n')
    write(tmp_path, ".ai/agents/09-security.md", PEM_HEADER + "\n")
    (tmp_path / "blob.bin").write_bytes(b"\x00\x01" + FAKE_AWS.encode())
    assert scan(tmp_path) == []


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (".env", True),
        (".env.local", True),
        ("prod.env", True),
        (".env.example", False),
        (".env.sample", False),
        ("environment.py", False),
    ],
)
def test_is_env_file(name: str, expected: bool) -> None:
    assert is_env_file(name) is expected
