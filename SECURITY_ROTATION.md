# Security Rotation Instructions

## Previously Committed Secrets & Artifacts
The following secret variable names and runtime artifacts were previously committed to git history and must be treated as compromised or leaked:
1. `SARTHI_HMAC_SECRET`
2. `SARTHI_API_TOKEN`
3. `SARTHI_SUPERVISOR_TOKEN`
4. `backend/checkpoints.db`

## Scrubbing Git History
To completely scrub these secrets and leaked artifacts from git history across all branches and commits, run the following commands using `git filter-repo`:

```bash
pip install git-filter-repo
git filter-repo --replace-text <(echo "SARTHI_HMAC_SECRET==>SCRUBBED" && echo "SARTHI_API_TOKEN==>SCRUBBED" && echo "SARTHI_SUPERVISOR_TOKEN==>SCRUBBED")
git filter-repo --invert-paths --path backend/checkpoints.db
```

After filtering, force-push to your remote repository:
```bash
git push origin --force --all
git push origin --force --tags
```
