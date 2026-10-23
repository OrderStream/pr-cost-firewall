"""
Unit and integration tests for pr-cost-firewall.
"""

import pytest
from pathlib import Path
from pr_cost_firewall.scanner import DockerfileAnalyzer, PythonASTCostAnalyzer, PRCostFirewall
from pr_cost_firewall.monetization import LicenseManager
from pr_cost_firewall.cli import main

def test_license_manager():
    comm = LicenseManager.get_tier(None)
    assert comm["tier"] == "community"

    ent = LicenseManager.get_tier("ord_ent_cost_pro")
    assert ent["tier"] == "enterprise"

    banner = LicenseManager.get_banner("pr-cost-firewall")
    assert "GABFQIK63R2NETJM7T673EAMZN4RJLLGP3OFUEJU5ZVTGWUKULZJNL6" in banner

def test_dockerfile_analyzer_catches_bloat(tmp_path):
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("""
FROM ubuntu:latest
WORKDIR /app
COPY . .
RUN npm install
RUN apt-get install -y curl
""", encoding="utf-8")

    violations = DockerfileAnalyzer.analyze(str(dockerfile), dockerfile.read_text(encoding="utf-8"))
    categories = [v.category for v in violations]
    descriptions = " ".join([v.description for v in violations])

    # Should catch missing .dockerignore, heavy base image, COPY . . before install, and uncleaned apt-get
    assert "Dockerfile Bloat" in categories
    assert "base image" in descriptions
    assert "cache invalidation" in descriptions
    assert "Uncleaned APT cache" in descriptions

def test_python_ast_catches_n_plus_one_and_llm(tmp_path):
    code_file = tmp_path / "service.py"
    code_file.write_text("""
def sync_users(users, db, openai):
    for u in users:
        # N+1 query
        data = db.query(u.id)
        # Unbounded LLM call in loop
        summary = openai.create(prompt=str(data))
""", encoding="utf-8")

    violations = PythonASTCostAnalyzer.analyze(str(code_file), code_file.read_text(encoding="utf-8"))
    categories = [v.category for v in violations]

    assert "Database N+1 Query Loop" in categories
    assert "Unbacked LLM Retry Loop" in categories

def test_pr_cost_firewall_markdown_generation(tmp_path):
    code_file = tmp_path / "bad.py"
    code_file.write_text("""
for item in items:
    db.query(item)
""", encoding="utf-8")

    violations = PRCostFirewall.scan_directory(str(tmp_path))
    assert len(violations) > 0
    comment = PRCostFirewall.generate_markdown_comment(violations, monthly_budget_threshold=50.0)
    assert "BLOCKED" in comment
    assert "+$" in comment

def test_cli_execution(tmp_path):
    # Test clean directory
    clean_dir = tmp_path / "clean"
    clean_dir.mkdir()
    good_file = clean_dir / "good.py"
    good_file.write_text("def add(a, b): return a + b\n", encoding="utf-8")

    exit_code = main(["scan", "--path", str(clean_dir), "--threshold", "50.0"])
    assert exit_code == 0

    exit_code_license = main(["license"])
    assert exit_code_license == 0
