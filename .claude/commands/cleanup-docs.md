# Documentation Cleanup Command

Clean up and reorganize project documentation to keep only essential files.

## Core Philosophy

**Keep only ESSENTIAL documentation:**
- Project overview (README)
- Architecture & technical design
- Setup guides (local + deployment)
- Strategy explanation
- Database migrations
- Future plans (ROADMAP)
- Version history (CHANGELOG)

**Archive or remove:**
- Step-by-step setup guides (GLM signup, Telegram setup, etc.)
- Historical planning documents
- Completed implementation plans
- Standalone bot documentation
- Marketing materials (keep in separate folder)

---

## Step 1: Identify Core Documentation

The ONLY files that should remain in `/docs`:

1. **README.md** - Documentation index
2. **ARCHITECTURE.md** - System architecture
3. **LOCAL_SETUP.md** - Local development setup
4. **RENDER_DEPLOYMENT.md** - Production deployment
5. **DATABASE_MIGRATIONS.md** - Migration system
6. **STRATEGY.md** - Trading strategies
7. **ROADMAP.md** - Future plans
8. **CHANGELOG.md** - Version history

Everything else should be:
- **Archived** (moved to `docs/archive/`) if it has historical value
- **Deleted** if it's truly obsolete
- **Consolidated** into core docs if the info is critical

---

## Step 2: Review Every .md File

For EACH .md file in the project (including nested folders):

1. **Show me the file path and first 20 lines**
2. **Categorize it:**
   - ✅ KEEP (one of the 8 core docs)
   - 📦 ARCHIVE (historical value but not current)
   - ❌ DELETE (obsolete with no value)
   - 🔄 CONSOLIDATE (extract critical info into core docs, then archive)

3. **Wait for my confirmation before moving/deleting**

---

## Step 3: Extract Critical Information

Before archiving setup guides or planning docs:

1. **Check if they contain critical info** that users need
2. **If yes:** Add a concise note to the relevant core doc
   - API signup instructions → Add URLs to LOCAL_SETUP.md
   - Deployment notes → Add to RENDER_DEPLOYMENT.md
   - Architecture decisions → Add to ARCHITECTURE.md

3. **Then archive** the original file

**Example:**
- `GLM_SIGNUP_GUIDE.md` has signup URL → Add URL to LOCAL_SETUP.md → Archive guide
- `TELEGRAM_SETUP.md` has @BotFather instructions → Add quick note to LOCAL_SETUP.md → Archive guide

---

## Step 4: Update Cross-References

After moving files:

1. **Update `docs/README.md`** to only list the 8 core docs
2. **Update all cross-references** in core docs to point to correct locations
3. **Add "Last Updated: [date]"** to any modified docs
4. **Verify all internal links work**

---

## Step 5: Organize Archive Folder

Structure `docs/archive/` clearly:

```
docs/archive/
├── setup-guides/           # GLM_SIGNUP_GUIDE.md, TELEGRAM_SETUP.md
├── planning/               # SAAS_TRANSFORMATION_PLAN.md, GLM_INTEGRATION_PLAN.md
├── standalone-bot/         # ENV_VARIABLES_STANDALONE.md, old deployment guides
└── completed/              # IMPLEMENTATION_COMPLETE.md, etc.
```

**OR** just keep flat with clear naming:
```
docs/archive/
├── ENV_VARIABLES_STANDALONE.md
├── GLM_SIGNUP_GUIDE.md
├── TELEGRAM_SETUP.md
├── SAAS_TRANSFORMATION_PLAN.md
└── ... (other historical docs)
```

---

## Step 6: Create/Update .claude/CLAUDE.md

Ensure `.claude/CLAUDE.md` exists and contains:

1. **Current system state** (what's working NOW)
2. **Recent changes** (last 30 days only)
3. **Key technical decisions** (architecture choices)
4. **Common pitfalls** (mistakes to avoid)
5. **File locations** (with line numbers for key functions)

**Length:** ~300-400 lines MAX (concise and focused)

**NOT included:** Historical planning, verbose explanations, completed features

---

## Step 7: Final Verification

Before completing:

1. ✅ **Count files in docs/:** Should be ~8-10 .md files ONLY
2. ✅ **Check archive/:** All non-core docs moved there
3. ✅ **Verify links:** All cross-references work
4. ✅ **Check dates:** All modified docs have "Last Updated"
5. ✅ **Test navigation:** User can find what they need from docs/README.md

---

## Success Criteria

**Task is complete when:**

1. ✅ Only 8-10 essential .md files in `docs/`
2. ✅ All setup guides archived (GLM, Telegram, etc.)
3. ✅ All planning docs archived
4. ✅ Critical info extracted to core docs
5. ✅ `docs/README.md` lists only core docs
6. ✅ `.claude/CLAUDE.md` created/updated
7. ✅ All cross-references verified
8. ✅ Summary provided with before/after file counts

---

## Output Format

After each major step, provide:

**Step X Summary:**
- Files reviewed: [count]
- Files archived: [list]
- Files deleted: [list]
- Files updated: [list with changes]
- Remaining: [list of files still in docs/]

**Final Summary:**
- Total files before: [count]
- Total files after: [count]
- Files archived: [count]
- Files deleted: [count]
- Core docs maintained: [list]

---

## Important Notes

- **NEVER delete without showing me first**
- **ALWAYS extract critical info before archiving**
- **ASK if unsure** whether something should be kept/archived/deleted
- **Show me the categorization list** before making changes
- **Preserve marketing materials** in `docs/socials/` (separate from docs)

---

**This command should result in clean, minimal, essential-only documentation.**
