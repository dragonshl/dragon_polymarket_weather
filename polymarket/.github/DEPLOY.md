# Deployment Guide

## Overview

This document describes how to deploy the Polymarket Weather Trading System using GitHub Actions.

## Deployment Environments

| Environment | Trigger | Description |
|---|---|---|
| `production` | Manual `workflow_dispatch` | Live trading system |
| `staging` | Manual `workflow_dispatch` | Test/validation |

**Note:** E2E tests run automatically on `main` branch pushes. Deployment is **manual only** — no auto-deploy to production.

---

## CI/CD Pipeline Stages

```
push/PR to main
      │
      ▼
┌─────────────┐
│    Lint     │  flake8 + black
│   (always)  │
└──────┬──────┘
       ▼
┌─────────────┐
│ Unit Tests  │  pytest (non-e2e)
│   (always)  │
└──────┬──────┘
       │
       ▼ (main push only)
┌─────────────┐
│   E2E Tests │  browser-use + Chrome
│  (main only)│
└──────┬──────┘
       │
       ▼ (PR + main push)
┌─────────────┐
│    Build    │  python -m build + zip artifact
│             │
└──────┬──────┘
       │
       ▼ (manual workflow_dispatch)
┌─────────────┐
│   Deploy    │  Download artifact + deploy steps
│  (manual)   │
└─────────────┘
```

---

## How to Trigger Deployment

### Via GitHub Web UI

1. Go to the repo → **Actions** tab
2. Select **CI/CD Pipeline**
3. Click **Run workflow**
4. Choose branch (`main`)
5. Select environment (`production` or `staging`)
6. Click **Run workflow**

### Via GitHub CLI

```bash
gh workflow run ci.yml \
  --field environment=production
```

---

## Required Secrets

Set these in **Settings → Secrets and variables → Actions**:

| Secret | Description | Required For |
|---|---|---|
| `AVWX_API_KEY` | AVWX METAR API key for weather data | Weather fetching |
| `POLYMARKET_API_KEY` | Polymarket CLOB API key | Trading |
| `POLYMARKET_PRIVATE_KEY` | Private key for signing orders | Trading |
| `OPENAI_API_KEY` | OpenAI key for browser-use E2E tests | E2E tests only |
| `DEPLOY_HOST` | Server hostname for deployment | Deployment |
| `DEPLOY_USER` | SSH username for deployment | Deployment |

### Adding Secrets

```bash
# Via GitHub CLI
gh secret set AVWX_API_KEY --body "your-key-here"
gh secret set POLYMARKET_API_KEY --body "your-key-here"
gh secret set POLYMARKET_PRIVATE_KEY --body "your-private-key-here"
gh secret set OPENAI_API_KEY --body "sk-..."
gh secret set DEPLOY_HOST --body "your-server.com"
gh secret set DEPLOY_USER --body "deploy-user"
```

Or via Web UI:
1. Repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Add each secret above

---

## Deployment Steps (What's Included)

1. **Artifact Download** — Downloads the built zip from the `build` stage
2. **Artifact Extraction** — Unzip to target server directory
3. **Environment Setup** — Install dependencies, configure env vars
4. **Service Restart** — Restart the trading bot service

### Customizing Deployment

Edit the `deploy` job in `.github/workflows/ci.yml`. Example for SSH deployment:

```yaml
- name: Deploy to server
  env:
    DEPLOY_HOST: ${{ secrets.DEPLOY_HOST }}
    DEPLOY_USER: ${{ secrets.DEPLOY_USER }}
  run: |
    echo "${{ secrets.DEPLOY_SSH_KEY }}" > deploy_key
    chmod 600 deploy_key
    scp -i deploy_key -o StrictHostKeyChecking=no \
      ./dist/polymarket-${{ github.sha }}.zip \
      ${{ secrets.DEPLOY_USER }}@${{ secrets.DEPLOY_HOST }}:/tmp/
    ssh -i deploy_key ${{ secrets.DEPLOY_USER }}@${{ secrets.DEPLOY_HOST }} \
      "cd /opt/polymarket && ./deploy.sh ${{ github.sha }}"
```

---

## Rollback Steps

If deployment fails:

1. **Identify the last good SHA:**
   ```bash
   git log --oneline -10
   ```

2. **Re-download artifact for good SHA:**
   - Go to Actions → find the good workflow run
   - Download the build artifact

3. **Deploy manually:**
   ```bash
   # On your server
   cd /opt/polymarket
   ./rollback.sh <good-sha>
   ```

4. **Or via GitHub Actions:**
   - Run workflow_dispatch for the good SHA

---

## Monitoring

- **CI Status:** Check the **Actions** tab for pipeline status
- **Logs:** Each job logs output; E2E tests capture browser logs
- **Artifact Retention:** Build artifacts are kept for 7 days

---

## Troubleshooting

### E2E tests fail in CI but pass locally

- CI runs headless Chrome (`HEADLESS=true`)
- Check `browser-use` + Chrome version compatibility
- Ensure `OPENAI_API_KEY` is set in repo secrets

### Deployment fails

- Verify all required secrets are set
- Check artifact was created (check `build` job)
- Verify server SSH connectivity

### Lint/Unit tests pass but E2E fails

- E2E requires `browser-use` + `langchain-openai` in `.venv`
- Install locally: `pip install browser-use langchain-openai`
- Run: `HEADLESS=false pytest tests/e2e/ -v` for headed debugging

---

## PMXT Relay Server Deployment

If deploying to PMXT relay:

```bash
# In deploy job
ssh ${{ secrets.DEPLOY_USER }}@${{ secrets.DEPLOY_HOST }} "
  cd /opt/pmxt-relay
  ./stop.sh
  unzip /tmp/polymarket-${{ github.sha }}.zip -d .
  ./start.sh
"
```