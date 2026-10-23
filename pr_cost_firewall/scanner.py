"""
Cost regression scanning engine analyzing Dockerfile bloat, N+1 DB loops, and LLM retry cost.
"""

import ast
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional

@dataclass
class CostViolation:
    category: str  # Dockerfile Bloat, DB N+1 Query, LLM Runaway
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    file_path: str
    line_number: int
    estimated_monthly_usd: float
    description: str
    remediation: str

class DockerfileAnalyzer:
    @staticmethod
    def analyze(file_path: str, content: str) -> List[CostViolation]:
        violations: List[CostViolation] = []
        lines = content.splitlines()

        # Check 1: Missing .dockerignore in directory
        dockerfile_dir = Path(file_path).parent
        dockerignore = dockerfile_dir / ".dockerignore"
        if not dockerignore.exists():
            violations.append(CostViolation(
                category="Dockerfile Bloat",
                severity="MEDIUM",
                file_path=file_path,
                line_number=1,
                estimated_monthly_usd=35.0,
                description="Missing .dockerignore file causes context upload of node_modules/.git to CI runner.",
                remediation="Create a .dockerignore file ignoring node_modules, target/, .git, and build artifacts."
            ))

        copy_all_line = None
        for idx, line in enumerate(lines, 1):
            clean = line.strip()
            if clean.startswith("#"):
                continue

            # Check 2: Heavy base images
            if re.match(r"^FROM\s+(ubuntu:latest|node:latest|python:latest|golang:latest)", clean, re.IGNORECASE):
                violations.append(CostViolation(
                    category="Dockerfile Bloat",
                    severity="HIGH",
                    file_path=file_path,
                    line_number=idx,
                    estimated_monthly_usd=28.0,
                    description=f"Using bloated base image '{clean}'. Inflates container registry storage and ECR egress bandwidth.",
                    remediation="Use minimal slim/alpine images: e.g., 'python:3.12-slim', 'node:20-alpine'."
                ))

            # Track COPY . . before install
            if re.match(r"^COPY\s+\.\s+\.", clean):
                copy_all_line = idx

            # Check 3: Dependencies installed after COPY . . (invalidates layer cache)
            if copy_all_line and re.search(r"RUN\s+(npm\s+install|pip\s+install|yarn\s+install|cargo\s+build)", clean, re.IGNORECASE):
                violations.append(CostViolation(
                    category="Dockerfile Bloat",
                    severity="CRITICAL",
                    file_path=file_path,
                    line_number=idx,
                    estimated_monthly_usd=65.0,
                    description="Layer cache invalidation: package installation occurs after 'COPY . .'. Forces full re-install on every commit.",
                    remediation="Copy package.json / requirements.txt first, run install, then copy source code."
                ))

            # Check 4: apt-get install without cleanup
            if "apt-get install" in clean and "rm -rf /var/lib/apt/lists" not in clean:
                violations.append(CostViolation(
                    category="Dockerfile Bloat",
                    severity="MEDIUM",
                    file_path=file_path,
                    line_number=idx,
                    estimated_monthly_usd=15.0,
                    description="Uncleaned APT cache: apt-get leaves index archives in image layers, increasing container image size by ~100MB.",
                    remediation="Append '&& rm -rf /var/lib/apt/lists/*' and use '--no-install-recommends'."
                ))

        return violations

class PythonASTCostAnalyzer:
    @staticmethod
    def analyze(file_path: str, content: str) -> List[CostViolation]:
        violations: List[CostViolation] = []
        try:
            tree = ast.parse(content, filename=file_path)
        except SyntaxError:
            return violations

        class LoopVisitor(ast.NodeVisitor):
            def __init__(self):
                self.in_loop = 0

            def visit_For(self, node: ast.For):
                self.in_loop += 1
                self.generic_visit(node)
                self.in_loop -= 1

            def visit_While(self, node: ast.While):
                self.in_loop += 1
                self.generic_visit(node)
                self.in_loop -= 1

            def visit_Call(self, node: ast.Call):
                if self.in_loop > 0:
                    func_name = ""
                    if isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr
                    elif isinstance(node.func, ast.Name):
                        func_name = node.func.id

                    # Check N+1 Database queries
                    db_methods = {"query", "execute", "filter", "find_one", "select", "all", "first", "fetchall"}
                    if func_name in db_methods:
                        violations.append(CostViolation(
                            category="Database N+1 Query Loop",
                            severity="CRITICAL",
                            file_path=file_path,
                            line_number=node.lineno,
                            estimated_monthly_usd=140.0,
                            description=f"Database query invocation '.{func_name}()' inside loop. Triggers N+1 query storm and forces expensive DB scaling.",
                            remediation="Eager load relations using 'select_related()' / 'joinedload()' or batch with 'WHERE id IN (...) / any()'."
                        ))

                    # Check LLM unbacked retry loops
                    llm_patterns = {"create", "generate_content", "chat", "complete", "messages"}
                    if func_name in llm_patterns:
                        # Check if caller looks like openai or anthropic or client
                        caller = ""
                        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                            caller = node.func.value.id
                        if caller in {"openai", "client", "anthropic", "genai", "model"}:
                            violations.append(CostViolation(
                                category="Unbacked LLM Retry Loop",
                                severity="CRITICAL",
                                file_path=file_path,
                                line_number=node.lineno,
                                estimated_monthly_usd=220.0,
                                description=f"Autonomous LLM API call '{caller}.{func_name}()' executed inside unbounded loop without exponential backoff or caching.",
                                remediation="Wrap with tenacity/backoff retry decorator, implement Redis prompt cache, and set max_retries limit."
                            ))

                self.generic_visit(node)

        visitor = LoopVisitor()
        visitor.visit(tree)
        return violations

class PRCostFirewall:
    @classmethod
    def scan_directory(cls, directory: str) -> List[CostViolation]:
        all_violations: List[CostViolation] = []
        dir_path = Path(directory)
        
        for file in dir_path.rglob("*"):
            if not file.is_file():
                continue
            
            # Skip hidden / venv
            parts = file.parts
            if any(p.startswith(".") or p in {"node_modules", "venv", ".git", "__pycache__"} for p in parts):
                continue

            try:
                # Dockerfile
                if file.name.lower().startswith("dockerfile"):
                    content = file.read_text(encoding="utf-8", errors="ignore")
                    all_violations.extend(DockerfileAnalyzer.analyze(str(file), content))
                # Python files
                elif file.suffix == ".py":
                    content = file.read_text(encoding="utf-8", errors="ignore")
                    all_violations.extend(PythonASTCostAnalyzer.analyze(str(file), content))
                # JS / TS files for simple regex N+1 pattern
                elif file.suffix in {".ts", ".js", ".tsx", ".jsx"}:
                    content = file.read_text(encoding="utf-8", errors="ignore")
                    cls._scan_js_ts(str(file), content, all_violations)
            except Exception:
                continue

        return all_violations

    @staticmethod
    def _scan_js_ts(file_path: str, content: str, violations: List[CostViolation]):
        lines = content.splitlines()
        in_loop = False
        loop_line = 0
        for idx, line in enumerate(lines, 1):
            if re.search(r"\b(for\s*\(|while\s*\(|\.forEach\s*\(|\.map\s*\()", line):
                in_loop = True
                loop_line = idx
            if in_loop and re.search(r"\b(prisma\.[a-zA-Z]+\.(findMany|findUnique|create|update)|db\.query|await\s+repository\.)", line):
                violations.append(CostViolation(
                    category="Database N+1 Query Loop",
                    severity="CRITICAL",
                    file_path=file_path,
                    line_number=idx,
                    estimated_monthly_usd=140.0,
                    description="Asynchronous DB query inside iteration loop. Triggers database connection pool exhaustion and spikes IOPS.",
                    remediation="Batch records using findMany({ where: { id: { in: ids } } }) or DataLoader."
                ))
            if "}" in line and in_loop and (idx - loop_line > 20):
                in_loop = False

    @staticmethod
    def generate_markdown_comment(violations: List[CostViolation], monthly_budget_threshold: float = 100.0) -> str:
        total_monthly_usd = sum(v.estimated_monthly_usd for v in violations)
        status_icon = "🚨 BLOCKED" if total_monthly_usd > monthly_budget_threshold else "⚠️ WARNING"
        if not violations:
            return (
                "### 🛡️ PR Cost Firewall: Clean Pass\n\n"
                "✅ No cloud cost regressions or architectural resource leaks detected."
            )

        md = [
            f"### {status_icon} Cloud Cost Regression Firewall Report",
            "",
            f"**Total Estimated Monthly AWS/Cloud Increase:** `+${total_monthly_usd:,.2f}/month`",
            f"**Budget Cap Threshold:** `${monthly_budget_threshold:,.2f}/month`",
            "",
            "| Severity | Category | File:Line | Est. Monthly Impact | Remediation |",
            "| :--- | :--- | :--- | :--- | :--- |"
        ]

        for v in violations:
            path_rel = v.file_path.replace("\\", "/")
            md.append(
                f"| `{v.severity}` | **{v.category}** | `{path_rel}:{v.line_number}` | **+${v.estimated_monthly_usd:,.2f}** | {v.remediation} |"
            )

        md.append("")
        md.append("---")
        md.append("> **Zero-Downtime Infrastructure Governance by OrderStream**")
        return "\n".join(md)
