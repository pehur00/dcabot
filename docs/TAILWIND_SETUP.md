# Tailwind CSS Setup

## Overview

This project uses **Tailwind CSS CLI** for production builds instead of the CDN. The build process generates a minified CSS file that includes only the utility classes actually used in the templates.

## Files

- `tailwind.config.js` - Tailwind configuration (custom colors, dark mode)
- `saas/static/css/tailwind.input.css` - Source CSS with Tailwind directives
- `saas/static/css/tailwind.output.css` - Generated CSS (gitignored, built on deployment)
- `build-tailwind.sh` - Build script that downloads Tailwind CLI and generates CSS

## Local Development

### First Time Setup

Run the build script to download Tailwind CLI and generate the CSS:

```bash
./build-tailwind.sh
```

This will:
1. Download the appropriate Tailwind CLI binary for your OS (macOS/Linux)
2. Make it executable
3. Build the production CSS from `tailwind.input.css` → `tailwind.output.css`

### Rebuilding After Template Changes

If you modify HTML templates or add new Tailwind classes, rebuild the CSS:

```bash
./build-tailwind.sh
```

### Watch Mode (Development)

For automatic rebuilding during development:

```bash
./tailwindcss -i ./saas/static/css/tailwind.input.css -o ./saas/static/css/tailwind.output.css --watch
```

## Production Deployment (Render)

The `render.yaml` build command automatically:
1. Downloads Tailwind CLI
2. Builds the CSS during deployment
3. Serves the static file from `saas/static/css/tailwind.output.css`

No manual intervention needed on Render.

## Custom Configuration

### Dark Mode
Configured with `darkMode: 'class'` - toggle with `.dark` class on `<html>` element.

### Custom Colors
Extended gray palette for dark UI:
- `gray-950`: #0a0a0a
- `gray-900`: #111111
- `gray-850`: #1a1a1a
- `gray-800`: #1f1f1f
- `gray-750`: #2a2a2a
- `gray-700`: #333333

### Custom Utilities
- `.scrollbar-hide` - Hides scrollbars while maintaining scrollability

## File Sizes

- **CDN Version**: ~3MB (includes all Tailwind classes)
- **Production Build**: ~39KB (only used classes, minified)

## Why Not CDN?

The CDN is meant for prototyping only. Production apps should use:
1. ✅ **Better Performance** - 39KB vs 3MB (98% smaller)
2. ✅ **No External Dependencies** - Faster load, no CORS issues
3. ✅ **No Console Warnings** - CDN shows "should not be used in production"
4. ✅ **Offline Development** - Works without internet after first build

## Troubleshooting

### CSS Not Updating
```bash
# Rebuild manually
./build-tailwind.sh

# Check output file exists
ls -lh saas/static/css/tailwind.output.css
```

### Build Fails on Render
- Check `render.yaml` includes: `chmod +x build-tailwind.sh && ./build-tailwind.sh`
- Verify `build-tailwind.sh` has correct Linux download URL
- Check Render build logs for errors

### Classes Not Working
- Ensure class names are in template files (Tailwind scans `saas/templates/**/*.html`)
- Rebuild CSS after adding new classes
- Check `tailwind.config.js` content paths are correct

## Migration from CDN

**Before:**
```html
<script src="https://cdn.tailwindcss.com"></script>
<script>tailwind.config = { ... }</script>
```

**After:**
```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/tailwind.output.css') }}">
```

All config moved to `tailwind.config.js` (JavaScript file).
