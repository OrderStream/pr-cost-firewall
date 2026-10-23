"""
Command line interface for pr-cost-firewall.
"""

import argparse
import sys
import json
from pathlib import Path
from pr_cost_firewall.scanner import PRCostFirewall
from pr_cost_firewall.monetization import LicenseManager

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="pr-cost-firewall",
        description="Pull Request cost regression scanner: Dockerfile bloat, N+1 queries, unbacked LLM retry loops"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # scan command
    scan_parser = subparsers.add_parser("scan", help="Scan directory or repository for cost regressions")
    scan_parser.add_argument("--path", default=".", help="Directory path to scan")
    scan_parser.add_argument("--threshold", type=float, default=100.0, help="Monthly USD cost increase threshold to trigger exit failure")
    scan_parser.add_argument("--output-comment", default=None, help="File path to save GitHub markdown comment")
    scan_parser.add_argument("--license-key", default=None, help="OrderStream license key")

    # comment command
    comment_parser = subparsers.add_parser("comment", help="Generate PR comment markdown for GitHub CI")
    comment_parser.add_argument("--path", default=".", help="Directory path to scan")
    comment_parser.add_argument("--threshold", type=float, default=100.0, help="Monthly USD threshold")

    # license / donate command
    subparsers.add_parser("license", help="View license tier and 0% fee crypto donation wallets")

    args = parser.parse_args(argv)

    if not args.command or args.command == "license":
        print(LicenseManager.get_banner("pr-cost-firewall"))
        tier = LicenseManager.get_tier(getattr(args, "license_key", None))
        print(f"Active Tier: {tier['name']} ({tier['tier']})")
        print(f"Features: {', '.join(tier['features'])}")
        print(LicenseManager.get_remediation_footer())
        return 0

    if args.command in {"scan", "comment"}:
        print(LicenseManager.get_banner("pr-cost-firewall"))
        violations = PRCostFirewall.scan_directory(args.path)
        total_cost = sum(v.estimated_monthly_usd for v in violations)
        comment_md = PRCostFirewall.generate_markdown_comment(violations, args.threshold)
        
        if args.command == "comment":
            print(comment_md)
            return 0

        print(f"[PR-COST-FIREWALL] Scanned: {args.path}")
        print(f"[PR-COST-FIREWALL] Total Violations: {len(violations)}")
        print(f"[PR-COST-FIREWALL] Estimated Monthly AWS/Cloud Cost Delta: +${total_cost:,.2f}/month")
        print(f"[PR-COST-FIREWALL] Threshold Cap: ${args.threshold:,.2f}/month")

        for v in violations:
            print(f"  [{v.severity}] {v.category} in {v.file_path}:{v.line_number} (+${v.estimated_monthly_usd:,.2f}/mo)")
            print(f"    Reason: {v.description}")
            print(f"    Fix:    {v.remediation}")

        if args.output_comment:
            Path(args.output_comment).write_text(comment_md, encoding="utf-8")
            print(f"[PR-COST-FIREWALL] Saved PR Markdown comment to: {args.output_comment}")

        print(LicenseManager.get_remediation_footer())

        if total_cost > args.threshold:
            print(f"\n❌ [PR-COST-FIREWALL] BLOCKED: Cost increase (+${total_cost:,.2f}) exceeds threshold (${args.threshold:,.2f})!")
            return 1
        
        print("\n✅ [PR-COST-FIREWALL] PASSED: Within cloud budget limit.")
        return 0

    return 0

if __name__ == "__main__":
    sys.exit(main())
