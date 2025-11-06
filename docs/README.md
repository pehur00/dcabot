# DCABot Documentation

**Last Updated:** November 6, 2025

Complete documentation for the DCABot SaaS Trading Platform.

---

## 📚 Documentation Index

### Essential Guides

| Document | Description |
|----------|-------------|
| **[../README.md](../README.md)** | Project overview and quick start guide |
| **[LOCAL_SETUP.md](LOCAL_SETUP.md)** | Local development environment setup |
| **[RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md)** | Production deployment on Render.com |
| **[STRATEGY.md](STRATEGY.md)** | Trading strategy explanations (Martingale + AI) |

### Technical Documentation

| Document | Description |
|----------|-------------|
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | System architecture and design decisions |
| **[DATABASE_MIGRATIONS.md](DATABASE_MIGRATIONS.md)** | Database migration system |
| **[ROADMAP.md](ROADMAP.md)** | Future features and planned improvements |
| **[CHANGELOG.md](CHANGELOG.md)** | Version history and release notes |

### Developer Resources

| Document | Description |
|----------|-------------|
| **[../saas/GOOGLE_OAUTH_SETUP.md](../saas/GOOGLE_OAUTH_SETUP.md)** | Configure Google OAuth authentication (for platform admins) |
| **[../scripts/README.md](../scripts/README.md)** | Helper scripts documentation |

### Archived Documents

| Folder | Contents |
|--------|----------|
| **[archive/](archive/)** | Historical planning docs (SaaS transformation plans, AI bot integration plans, multi-strategy plans, standalone bot deployment guides) |

---

## 🚀 Quick Navigation

### I want to...

**...get started quickly**
→ Read [../README.md](../README.md) → [LOCAL_SETUP.md](LOCAL_SETUP.md)

**...deploy to production**
→ Read [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md)

**...understand the trading strategies**
→ Read [STRATEGY.md](STRATEGY.md)

**...understand the system architecture**
→ Read [ARCHITECTURE.md](ARCHITECTURE.md)

**...set up API keys for trading bots**
→ Configure in dashboard Settings page (see [LOCAL_SETUP.md](LOCAL_SETUP.md))

**...see what's planned for the future**
→ Read [ROADMAP.md](ROADMAP.md)

**...run database migrations**
→ Read [DATABASE_MIGRATIONS.md](DATABASE_MIGRATIONS.md)

---

## 📂 Documentation Structure

```
docs/
├── README.md                     # This file (documentation index)
│
├── Essential Guides/
│   ├── LOCAL_SETUP.md            # Local development setup
│   ├── RENDER_DEPLOYMENT.md      # Production deployment
│   └── STRATEGY.md               # Trading strategies
│
├── Technical Docs/
│   ├── ARCHITECTURE.md           # System architecture
│   ├── DATABASE_MIGRATIONS.md    # Migration system
│   ├── ROADMAP.md                # Future plans
│   └── CHANGELOG.md              # Version history
│
├── Developer Resources/
│   └── ../saas/GOOGLE_OAUTH_SETUP.md  # OAuth setup (admins only)
│
├── socials/                      # Marketing materials
│   └── examples/                 # Reddit posts, social media content
│
└── archive/                      # Archived documents
    ├── Setup guides (GLM_SIGNUP_GUIDE.md, TELEGRAM_SETUP.md)
    ├── ENV_VARIABLES_STANDALONE.md  # Standalone bot env vars
    ├── Planning docs (SAAS_TRANSFORMATION_PLAN.md, etc.)
    └── ... (historical documents)
```

---

## 🔗 External Resources

- **GitHub Repository:** https://github.com/pehur00/dcabot
- **Render Dashboard:** https://dashboard.render.com
- **Phemex API Docs:** https://phemex-docs.github.io/
- **GLM API Docs:** https://bigmodel.cn/dev/api
- **DeepSeek API:** https://platform.deepseek.com/
- **Anthropic Claude API:** https://docs.anthropic.com/

---

## 💡 Documentation Tips

- **Start with [../README.md](../README.md)** for project overview
- **Use [LOCAL_SETUP.md](LOCAL_SETUP.md)** for safe testing before deploying
- **Read [STRATEGY.md](STRATEGY.md)** to understand risk management
- **Check [../CLAUDE_BACKGROUND.md](../.claude/CLAUDE.md)** for AI development context
- **All planning documents** are in `archive/` for reference

---

## 📝 Contributing to Documentation

When updating docs:
1. Keep the last updated date current
2. Ensure cross-references are valid
3. Use clear, concise language
4. Include code examples where helpful
5. Archive outdated docs instead of deleting

---

**Need help?** Check the main [README.md](../README.md) or open an issue on GitHub.
