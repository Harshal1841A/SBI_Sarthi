# Security Rotation Instructions

## Previously Committed Secrets
The following secret variable names were previously committed to git history and must be treated as compromised:
1. `SARTHI_HMAC_SECRET`
2. `SARTHI_API_TOKEN`
3. `SARTHI_SUPERVISOR_TOKEN`

## Scrubbing Git History
To completely scrub these secrets and their historical values from git history across all branches and commits, run the following command using `git filter-repo`:

```bash
pip install git-filter-repo
git filter-repo --replace-text <(echo "SARTHI_HMAC_SECRET==>SCRUBBED" && echo "SARTHI_API_TOKEN==>SCRUBBED" && echo "SARTHI_SUPERVISOR_TOKEN==>SCRUBBED")
```

After filtering, force-push to your remote repository:
```bash
git push origin --force --all
git push origin --force --tags
```
