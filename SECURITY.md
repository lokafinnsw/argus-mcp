# 🔒 Security Guidelines

## ⚠️ CRITICAL: API Keys Protection

**NEVER commit files with real API keys to GitHub!**

### Protected Files (Already in .gitignore)

These files contain real API keys and are automatically ignored:

- ✅ `.env` - Your environment variables
- ✅ `test_*.py` - Test files with hardcoded keys
- ✅ `server.py` - Old server version with hardcoded keys
- ✅ `mcp_config_example.json` - Config with real paths/keys
- ✅ `test_local.py` - Local test file

### Safe Files (Can be committed)

- ✅ `.env.example` - Template without real keys
- ✅ `test_example.py` - Example test without keys
- ✅ `server_v2.py` - Production server (reads from .env)
- ✅ All other source files

## 🛡️ Before Pushing to GitHub

### 1. Check for leaked keys

```bash
# Search for your API keys in all files
grep -r "your_actual_api_key" .

# Should return NOTHING or only .env (which is gitignored)
```

### 2. Verify .gitignore works

```bash
# Initialize git if not done
git init

# Check what will be committed
git status

# These should NOT appear:
# - .env
# - test_*.py (except test_example.py)
# - server.py
# - mcp_config_example.json
```

### 3. Test .gitignore

```bash
# This should show ignored files
git status --ignored

# Verify .env and test files are in the ignored list
```

## 🔑 How to Use API Keys Safely

### For Development

1. Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

2. Edit `.env` with your real keys:
```bash
GLM_API_KEY=your_real_glm_key
OPENROUTER_API_KEY=your_real_openrouter_key
```

3. Never commit `.env` (already in .gitignore)

### For Testing

1. Copy `test_example.py` to `test_local.py`:
```bash
cp test_example.py test_local.py
```

2. Add your keys to `test_local.py`

3. Run tests:
```bash
python test_local.py
```

4. `test_local.py` is automatically ignored by git

## 🚨 If You Accidentally Committed Keys

### Immediate Actions

1. **Revoke the exposed keys immediately:**
   - GLM API: https://api.z.ai → Regenerate key
   - OpenRouter: https://openrouter.ai/keys → Delete & create new

2. **Remove from git history:**
```bash
# Remove file from git history
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all

# Force push (DANGEROUS - only if repo is private/new)
git push origin --force --all
```

3. **Update .env with new keys**

## ✅ Security Checklist

Before pushing to GitHub:

- [ ] `.env` is in `.gitignore`
- [ ] No API keys in source code
- [ ] `.env.example` has only placeholders
- [ ] Test files with keys are gitignored
- [ ] `git status` shows no sensitive files
- [ ] Searched codebase for actual key strings

## 📝 Reporting Security Issues

If you find a security vulnerability, please email:
- **DO NOT** open a public issue
- Contact: [your-email@example.com]

## 🔐 Best Practices

1. **Use environment variables** - Never hardcode keys
2. **Rotate keys regularly** - Change API keys every 90 days
3. **Limit key permissions** - Use read-only keys when possible
4. **Monitor usage** - Check API usage for anomalies
5. **Use .env files** - Keep keys separate from code

---

**Remember: Once a key is on GitHub, consider it compromised!**
