# Tailwind CSS Setup

## Overview

This project uses **Tailwind CSS v4** with the standalone CLI for production builds. Tailwind v4 uses **CSS-based configuration** instead of JavaScript config files.

## Files

- `saas/static/css/tailwind.input.css` - Source CSS with Tailwind v4 directives and theme configuration
- `saas/static/css/tailwind.output.css` - Generated CSS (gitignored, built on deployment)
- `build-tailwind.sh` - Build script that downloads Tailwind CLI and generates CSS

## Tailwind v4 Changes

**What's New:**
- Configuration in CSS using `@theme` directive (no more `tailwind.config.js`)
- Faster builds with native Rust/Oxide engine
- Better CSS-in-JS support
- Native nesting support

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

## Custom Configuration (Tailwind v4)

All configuration is done in `saas/static/css/tailwind.input.css` using CSS directives.

### Custom Theme Colors

```css
@theme {
    --color-gray-950: #0a0a0a;
    --color-gray-900: #111111;
    --color-gray-850: #1a1a1a;
    --color-gray-800: #1f1f1f;
    --color-gray-750: #2a2a2a;
    --color-gray-700: #333333;
}
```

Use in HTML: `bg-gray-950`, `text-gray-850`, `border-gray-700`, etc.

### Custom Utilities

```css
@utility scrollbar-hide {
    -ms-overflow-style: none;
    scrollbar-width: none;

    &::-webkit-scrollbar {
        display: none;
    }
}
```

Use in HTML: `overflow-x-auto scrollbar-hide`

## File Sizes

- **CDN Version**: ~3MB (includes all Tailwind classes)
- **Production Build v4**: ~16KB (only used classes, minified, faster engine)

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
