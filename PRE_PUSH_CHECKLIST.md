# 🔒 PRE-PUSH SECURITY CHECKLIST

**CRITICAL: Complete this checklist BEFORE pushing to GitHub!**

## ✅ Files to Commit (SAFE)

These files are clean and safe to publish:

- [x] `server_v2.py` - Production server (reads from .env)
- [x] `config.py` - Configuration (reads from .env)
- [x] `validators.py` - Input validation
- [x] `models.py` - Model management
- [x] `prompts.py` - Prompt templates
- [x] `cache.py` - Caching logic
- [x] `.env.example` - Template (NO real keys)
- [x] `requirements.txt` - Dependencies
- [x] `LICENSE` - MIT License
- [x] `CONTRIBUTING.md` - Contribution guide
- [x] `SECURITY.md` - Security guidelines
- [x] `.gitignore` - Git ignore rules
- [x] `.gitattributes` - Language detection
- [x] `test_example.py` - Safe test template
- [x] `README_FINAL.md` - Clean documentation (rename to README.md)
- [x] `assets/` - Screenshots folder

## ❌ Files to IGNORE (DANGEROUS)

These files contain sensitive data and MUST NOT be committed:

- [ ] `.env` - Your real API keys
- [ ] `test_*.py` - All test files with hardcoded keys
- [ ] `server.py` - Old version with hardcoded keys
- [ ] `README.md` - Old version with personal paths
- [ ] `README_V2.md` - Old version with personal paths
- [ ] `MIGRATION.md` - Contains personal paths
- [ ] `GITHUB_SETUP.md` - Contains personal paths
- [ ] `mcp_config_example.json` - Contains real keys (already cleaned)

## 🔍 Final Security Check

Run these commands BEFORE pushing:

```bash
# 1. Search for your API keys
grep -r "319f2a73486546838f9d7425bf79d5de" . --exclude-dir=venv --exclude-dir=.git
grep -r "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" . --exclude-dir=venv --exclude-dir=.git

# Should return ONLY files in .gitignore (test_*.py, server.py, etc.)

# 2. Search for personal paths
grep -r "/Users/andresvlc" . --exclude-dir=venv --exclude-dir=.git --include="*.md" --include="*.py" --include="*.json"

# Should return ONLY files in .gitignore

# 3. Check what will be committed
git status

# Should NOT show: .env, test_*.py, server.py, old README files

# 4. Check ignored files
git status --ignored

# Should show: .env, test_*.py, server.py in ignored list
```

## 📝 Pre-Push Commands

```bash
# 1. Rename final README
mv README_FINAL.md README.md

# 2. Initialize git (if not done)
git init

# 3. Add remote
git remote add origin https://github.com/lokafinnsw/argus-mcp.git

# 4. Add files
git add .

# 5. VERIFY what will be committed
git status

# 6. Commit
git commit -m "Initial commit: Argus MCP v2.0.0

- Zero-Trust code review approach
- Support for 3 AI models (GLM 4.7, Gemini 3 Flash, MiniMax)
- Retry with exponential backoff
- Intelligent caching (1h TTL)
- Language-aware checks for 10+ languages
- 4 MCP tools: verify_code, list_models, set_default_model, cache_stats
- Multilingual support (English, Russian, Chinese, etc.)
- Compatible with Windsurf, Claude Desktop, Cursor"

# 7. Push to GitHub
git branch -M main
git push -u origin main
```

## ⚠️ If You Find Leaked Keys

**STOP IMMEDIATELY!**

1. **DO NOT PUSH**
2. Remove the file from git:
   ```bash
   git rm --cached <filename>
   ```
3. Add to `.gitignore`
4. Commit the removal
5. **Revoke the exposed keys:**
   - GLM API: https://api.z.ai
   - OpenRouter: https://openrouter.ai/keys
6. Generate new keys
7. Update `.env` with new keys

## ✅ Final Verification

Before pushing, answer these questions:

- [ ] Did you search for API keys? (None found in committed files?)
- [ ] Did you search for personal paths? (None found in committed files?)
- [ ] Did you check `git status`? (No sensitive files listed?)
- [ ] Did you rename README_FINAL.md to README.md?
- [ ] Is `.env` in .gitignore?
- [ ] Are all test_*.py files in .gitignore?
- [ ] Is server.py in .gitignore?
- [ ] Did you verify mcp_config_example.json has NO real keys?

## 🎉 Ready to Push!

If all checks pass, you're ready to push to GitHub!

```bash
git push -u origin main
```

---

**Repository:** https://github.com/lokafinnsw/argus-mcp.git

**Remember:** Once pushed, consider ALL exposed keys compromised!
