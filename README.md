# pr-cost-firewall 💸🔥

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://img.shields.io/badge/CI-Passing-brightgreen.svg)]()
[![OrderStream Polar](https://img.shields.io/badge/Polar-OrderStream-blue.svg)](https://polar.sh/orderstream)
[![Stellar XLM/USDC](https://img.shields.io/badge/Stellar-USDC%2FXLM-black.svg)](#direct-web3-wallet-monetization)
[![Base USDC](https://img.shields.io/badge/Base-USDC-0052FF.svg)](#direct-web3-wallet-monetization)

Pull Request cost regression scanner that analyzes Dockerfile bloat, unindexed DB query loops (N+1), and unbacked LLM retry loops, commenting on PRs with estimated AWS/cloud monthly cost increases.

---

## 💥 The Friction & Dollar Cost
Cloud bills rarely explode from intentional architectural changes—they explode from sneaky 3-line regressions in PRs:
1. **Dockerfile Layer Invalidation**: `COPY . .` placed before `RUN npm install` busts Docker cache on every commit, turning 30-second builds into 12-minute runner rebuilds and ballooning container registry storage (`+$65/month`).
2. **Database N+1 Query Storms**: An ORM call (`db.query()`, `prisma.findMany()`) slipped into a loop spikes RDS IOPS, forcing an unbudgeted database tier upgrade (`+$140/month`).
3. **Unbounded LLM Retry Loops**: Autonomous agent retry loops without exponential backoff or caching hammering OpenAI / Anthropic APIs (`+$220/month`).

**pr-cost-firewall** catches these regressions before merge in CI, calculates the estimated dollar impact, and comments directly on the PR.

---

## 🚀 Quick Start

### Installation
```bash
pip install pr-cost-firewall
```

### CLI Usage
```bash
# Scan current repository
pr-cost-firewall scan

# Enforce a maximum $100/mo cost delta threshold (fails CI if exceeded)
pr-cost-firewall scan --path . --threshold 100.0

# Export PR Markdown comment table
pr-cost-firewall comment --path . > pr_comment.md

# View license & zero-fee wallet payment details
pr-cost-firewall license
```

---

## 🤖 GitHub Action Integration

```yaml
- name: Cloud Cost Regression Firewall
  uses: OrderStream/pr-cost-firewall@v1
  with:
    path: "."
    threshold: "75.0"
    comment_on_pr: true
```

---

## 💰 Direct Web3 Wallet Monetization & Polar Integration

Support this project or purchase enterprise cloud tariff modeling with **0 platform fees**:

- **Polar Subscription & Sponsorship:** [https://polar.sh/orderstream](https://polar.sh/orderstream)
- **Stellar Network (Native XLM / USDC):**
  - Public Key: `GABFQIK63R2NETJM7T673EAMZN4RJLLGP3OFUEJU5ZVTGWUKULZJNL6`
  - Memo (Required): `400566831`
- **EVM (Base / Arbitrum / Ethereum USDT & USDC):**
  - Address: `0x5de2b62434754bfd39ef350a3a867ed3eced5074`
