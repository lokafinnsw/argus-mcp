# Contributing to Argus MCP

Thank you for your interest in contributing to Argus MCP! 🔱

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/argus-mcp.git`
3. Create a virtual environment: `python3 -m venv venv`
4. Install dependencies: `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and add your API keys

## Development Workflow

1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Test your changes: `python test_v2.py`
4. Check syntax: `python -m py_compile *.py`
5. Commit with clear messages: `git commit -m "Add: feature description"`
6. Push to your fork: `git push origin feature/your-feature-name`
7. Open a Pull Request

## Code Style

- Follow PEP 8 for Python code
- Use type hints where possible
- Add docstrings to functions and classes
- Keep functions focused and small
- Comment complex logic

## Adding a New Language

To add language-specific checks, edit `prompts.py`:

```python
LANGUAGE_HINTS = {
    ".rb": """
**Ruby-specific checks:**
- Ruby style guide compliance
- Blocks and procs usage
- ...
"""
}
```

## Adding a New Model

To add a new AI model, edit `config.py`:

```python
MODELS = {
    "new-model": {
        "name": "New Model Name",
        "provider": "provider_name",
        "api_key": NEW_MODEL_API_KEY,
        "base_url": "https://api.provider.com",
        "model_id": "model-id",
        "enabled": bool(NEW_MODEL_API_KEY),
        "cost_per_1k_tokens": 0.0,
        "max_tokens": 8000,
        "timeout": 60
    }
}
```

## Testing

Before submitting a PR, ensure all tests pass:

```bash
# Test all functionality
python test_v2.py

# Test specific features
python test_gemini.py
python test_minimax.py
python test_set_model.py
python test_new_prompt.py
```

## Pull Request Guidelines

- **Title**: Clear and descriptive (e.g., "Add: Support for Ruby language checks")
- **Description**: Explain what and why
- **Tests**: Include tests for new features
- **Documentation**: Update README if needed

## Commit Message Format

```
Type: Brief description

Detailed explanation (if needed)

Types: Add, Fix, Update, Remove, Refactor, Docs, Test
```

Examples:
- `Add: Support for Rust language checks`
- `Fix: Cache not clearing after TTL expiration`
- `Update: Gemini model to latest version`

## Questions?

Feel free to open an issue for:
- Bug reports
- Feature requests
- Questions about implementation
- Documentation improvements

## Code of Conduct

- Be respectful and constructive
- Focus on the code, not the person
- Help others learn and grow
- Keep discussions professional

Thank you for contributing! 🙏
