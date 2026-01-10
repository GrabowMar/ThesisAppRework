# 🔒 Security Key Rotation Guide

## ⚠️ CRITICAL: Exposed API Keys Detected

Your API keys were committed to the Git repository and are now compromised. Follow this guide to rotate all credentials.

---

## 📋 Keys That Need Immediate Rotation

| Service | Key Type | Status |
|---------|----------|--------|
| OpenRouter | API Key | 🔴 **EXPOSED** - Rotate immediately |
| HuggingFace | Access Token | 🔴 **EXPOSED** - Rotate immediately |
| Internal API | Application Key | 🔴 **EXPOSED** - Regenerate immediately |

---

## 🔄 Step-by-Step Rotation Process

### 1. OpenRouter API Key

**Old Key (COMPROMISED):** `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`

**Steps:**
1. Go to [OpenRouter Keys Page](https://openrouter.ai/keys)
2. **Revoke** the old key immediately
3. Generate a new API key
4. Copy the new key to your `.env` file:
   ```bash
   OPENROUTER_API_KEY=your_new_key_here
   ```

---

### 2. HuggingFace Token

**Old Token (COMPROMISED):** `[REDACTED]`

**Steps:**
1. Go to [HuggingFace Tokens Page](https://huggingface.co/settings/tokens)
2. Find and **delete** the compromised token
3. Create a new access token with appropriate permissions
4. Copy the new token to your `.env` file:
   ```bash
   HF_TOKEN=your_new_token_here
   ```

---

### 3. Internal Application API Key

**Old Key (COMPROMISED):** `DZHnCEy0b2rkWu6RI8wDMgSZ2NTSPNOLMVr7AU-HqcqgghDmLoZfN2XMYEz4FVsT`

**Steps:**
1. Generate a new secure random key:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```
2. Copy the generated key to your `.env` file:
   ```bash
   API_KEY_FOR_APP=your_new_generated_key_here
   ```
3. If you have any API clients using the old key, update them with the new key

---

### 4. Generate Flask Secret Key (if not set)

Generate a secure secret key for Flask sessions:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Add to your `.env` file:
```bash
SECRET_KEY=your_generated_secret_key_here
```

---

## 🧹 Clean Up Git History

The exposed keys are in your Git history. You need to remove them:

### Option 1: If You Haven't Pushed to Remote (Recommended)

If this repository is only local or you control all remotes:

```bash
# Remove the .env file from Git history
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all

# Force push if you've already pushed (WARNING: coordinate with team)
git push origin --force --all
```

### Option 2: If Repository is Public or Shared

If the repository has been pushed to a public/shared remote:

1. **Assume all keys are compromised** (you've already rotated them ✓)
2. Consider the commit history as public forever
3. Add a note in your README about the security incident
4. Make sure `.env` is properly in `.gitignore` going forward

### Option 3: BFG Repo-Cleaner (Easier Alternative)

```bash
# Install BFG Repo-Cleaner
# Download from: https://rtyley.github.io/bfg-repo-cleaner/

# Remove .env from entire history
bfg --delete-files .env

# Clean up
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

---

## ✅ Verification Checklist

After rotating all keys, verify:

- [ ] All old keys have been revoked/deleted from service providers
- [ ] New keys are saved in `.env` (NOT committed to Git)
- [ ] `.env` is listed in `.gitignore` (already done ✓)
- [ ] `.env.example` template is committed (already done ✓)
- [ ] Application starts successfully with new keys
- [ ] No errors in logs related to authentication
- [ ] Git history cleaned (if using Option 1 or 3)

Test your application:
```bash
# Start the application
python run.py

# Check logs for authentication errors
tail -f logs/app.log
```

---

## 🛡️ Prevention: Best Practices Going Forward

### 1. Pre-Commit Hooks

Install a pre-commit hook to prevent secrets from being committed:

```bash
# Install detect-secrets
pip install detect-secrets

# Create a baseline
detect-secrets scan > .secrets.baseline

# Add to .pre-commit-config.yaml
```

### 2. Environment File Management

- ✅ **DO:** Keep `.env` in `.gitignore`
- ✅ **DO:** Commit `.env.example` with placeholder values
- ✅ **DO:** Document required environment variables
- ❌ **DON'T:** Commit `.env`, `.env.local`, `.env.production`
- ❌ **DON'T:** Share `.env` files via email/Slack
- ❌ **DON'T:** Include real credentials in code comments

### 3. Use a Secrets Manager (Production)

For production deployments, consider:

- **AWS Secrets Manager**
- **HashiCorp Vault**
- **Azure Key Vault**
- **Google Cloud Secret Manager**
- **Docker Secrets** (for Docker Swarm)
- **Kubernetes Secrets** (for K8s deployments)

### 4. Regular Security Audits

Schedule regular security checks:

```bash
# Check for exposed secrets
git log -p | grep -E '(api_key|secret|password|token)' -i

# Scan codebase for secrets
detect-secrets scan --all-files

# Check dependencies for vulnerabilities
pip-audit
```

---

## 📞 Support

If you suspect unauthorized access or usage:

- **OpenRouter:** Check usage at https://openrouter.ai/activity
- **HuggingFace:** Review API usage in settings
- **Monitor logs:** Check application logs for suspicious activity

---

## 📚 Additional Resources

- [OWASP Secret Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [GitHub: Removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
- [Git Filter-Repo](https://github.com/newren/git-filter-repo) - Modern alternative to filter-branch

---

**Last Updated:** 2026-01-10
**Status:** 🔴 Action Required - Keys need rotation
