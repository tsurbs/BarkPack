---
name: ScottyLabs Design System
description: Comprehensive guide for building ScottyLabs web applications following the official design system
---

# ScottyLabs Design System

## Philosophy

The ScottyLabs Design System bridges imagination and implementation. It provides a robust foundation for creative expression while ensuring every ScottyLabs product "feels" like it belongs to the same family. It is **opt-in** — CMU-branded projects (CMU Maps, CMU Eats, CMU Courses) typically opt-in, but experimental projects may deviate.

---

## Typography

| Typeface         | Role                | Usage                                              |
|------------------|---------------------|----------------------------------------------------|
| **Satoshi**      | Primary / display   | All text by default — headings, body, UI labels    |
| **JetBrains Mono** | Monospace / code  | Code blocks, decorative detail text, annotations   |
| **Inter**        | Secondary option    | Alternative for body text / UI where needed        |

**Font weight default:** `500` (medium).  
**Heading weight:** `700` (bold).

### Type Scale (CSS custom properties)

```css
--text-xs:  0.75rem;   /* 12px */
--text-sm:  0.875rem;  /* 14px */
--text-base: 1rem;     /* 16px */
--text-lg:  1.125rem;  /* 18px */
--text-xl:  1.25rem;   /* 20px */
--text-2xl: 1.5rem;    /* 24px */
--text-3xl: 1.875rem;  /* 30px */
--text-4xl: 2.25rem;   /* 36px */
--text-5xl: 2.75rem;   /* 44px */
--text-6xl: 3.75rem;   /* 60px */
--text-9xl: 6rem;      /* 96px */
```

### Heading defaults
- `h1` → `--text-5xl`
- `h2` → `--text-3xl`
- `h3` → `--text-xl`
- `p` → `--text-lg`
- `small` → `--text-xs`

---

## Color System

All colors are defined as HSL values in CSS custom properties.

### Neutral Scale (black-*)

| Token          | HSL Value             | Rough Hex  | Usage                            |
|----------------|-----------------------|------------|----------------------------------|
| `--black-50`   | `hsl(0, 0%, 97%)`    | `#f7f7f7`  | Hover backgrounds, subtle fills  |
| `--black-100`  | `hsl(0, 0%, 93%)`    | `#ededed`  | Borders, section backgrounds     |
| `--black-200`  | `hsl(0, 0%, 89%)`    | `#e3e3e3`  | Decorative lines, dividers       |
| `--black-300`  | `hsl(0, 0%, 70%)`    | `#b3b3b3`  | Muted text, subtle borders       |
| `--black-400`  | `hsl(0, 0%, 50%)`    | `#808080`  | Secondary text                   |
| `--black-500`  | `hsl(0, 0%, 35%)`    | `#595959`  | Body text, descriptions          |
| `--black-900`  | `hsl(0, 0%, 0%)`     | `#000000`  | Primary text, headings           |

### Blue Scale

| Token          | HSL Value               | Rough Hex  | Usage                        |
|----------------|--------------------------|------------|------------------------------|
| `--blue-50`    | `hsl(200, 23%, 97%)`    | `#f4f7f9`  | Panel backgrounds            |
| `--blue-300`   | `hsl(230, 50%, 80%)`    | `#aab3e6`  | Focus outlines               |
| `--blue-600`   | `hsl(226, 76%, 50%)`    | `#1f47e0`  | Links, repo labels           |

### Accent Colors

| Token          | Value                  | Usage                          |
|----------------|------------------------|--------------------------------|
| `--red-500`    | `hsl(0, 70%, 50%)`    | Accent red, warnings           |
| `#24a4ff`      | —                      | Decorative borders, highlights |

### Brand Gradient (Footer / Decorative)

```css
/* Primary brand gradient — footer border, decorative accents */
linear-gradient(90deg, #ff004e 0%, #4f2485 54%, #40d2fc 100%)

/* Tab underline gradient */
linear-gradient(90deg, #36a5f2 0%, #d28dff 47.12%, #ff8d8d 99.52%)
```

### TartanHacks Colors (Event-specific)

| Token              | Value      | Usage                        |
|--------------------|------------|------------------------------|
| Background         | `#120902`  | Dark event card background   |
| Border / accent    | `#90662e`  | Gold border                  |
| Text / highlight   | `#fdc274`  | Gold text on dark background |

---

## Layout & Spacing

### Core Rules
- **Even-number spacing:** All paddings/margins in **multiples of 2**. No decimals.
- **Max container width:** `1200px` (content sections) / `1300–1400px` (header/footer)
- **Section padding:** `padding-inline: 40px`
- **Content centering:** `margin-inline: auto` with `max-width: var(--max-container-width)`

### Border Radius Tokens

| Token                    | Value   | Usage                    |
|--------------------------|---------|--------------------------|
| `--border-radius-base`   | `10px`  | Cards, inputs, panels    |
| `--border-radius-lg`     | `40px`  | Buttons, pills           |

### Centered Section Pattern

```css
.centered-section {
  --padding: 40px;
  --max-container-width: 1200px;
  padding-inline: var(--padding);
  margin-inline: auto;
  max-width: var(--max-container-width);
}
```

---

## Component Patterns

### Buttons

```css
.button {
  border: 1px solid transparent;
  font-weight: 700;
  font-size: var(--text-xl);
  padding: 12px 33px;
  border-radius: var(--border-radius-lg);  /* 40px — pill shape */
}
/* Primary: dark bg, light text */
.primary {
  background-color: var(--black-900);
  color: var(--black-50);
}
/* Outlined: transparent bg, dark border */
.outlined {
  border-color: var(--black-900);
  color: var(--black-900);
}
/* Hover animation */
.button--animated {
  transition: 0.15s transform;
}
.button--animated:hover {
  transform: scale(1.05);
}
.button--animated:hover:active {
  transform: scale(1.02);
}
```

### Navigation

```css
.nav-button {
  display: flex;
  gap: 4px;
  padding: 10px 13px;
  font-size: var(--text-base);
  align-items: center;
  color: var(--black-900);
  border: 1px solid transparent;
  border-radius: var(--border-radius-base);
}
.nav-button:hover {
  background-color: var(--black-50);
}
.nav-button--active {
  background-color: var(--blue-50);
  border-color: var(--black-200);
}
```

### Header

```css
/* Sticky header with backdrop blur */
.main-header-container {
  position: sticky;
  top: 0;
  backdrop-filter: blur(40px);
  background: rgba(255, 255, 255, 0.809);
  z-index: 999;
}
```

### Cards / Panels

```css
.panel-container {
  border-radius: 11px;
  border: 1px solid var(--black-100);
  box-shadow: 0 4px 4px 0 rgba(0, 0, 0, 0.25);
  overflow: hidden;
}
.panel__details {
  padding: 35px 25px;
  background-color: var(--blue-50);
  border-left: 5px solid var(--black-100);
}
```

### Contributor Pills

```css
.contributor-pill {
  border-radius: 20px;
  border: 1px solid var(--black-300);
  padding: 5px 20px 5px 5px;
  font-size: 1.25rem;
  color: var(--black-900);
}
.contributor-pill:hover {
  background-color: var(--black-50);
}
```

---

## Animation Patterns

| Effect               | Timing                                         | Usage                    |
|----------------------|------------------------------------------------|--------------------------|
| Button scale         | `0.15s transform`                              | Hover: 1.05, Active: 1.02 |
| Background transition| `0.15s background-color`                       | Nav items, pills         |
| Border color         | `0.15s border-color`                           | Tab underlines           |
| Tab indicator        | `0.5s cubic-bezier(0.27, 1.32, 0.41, 1)`      | Sliding underline        |
| Outline offset       | `0.1s all`                                     | Calendar hover           |
| Popup fade-in        | `0.2s ease-out`                                | Tooltip popups           |

---

## Global Resets & Defaults

```css
:root {
  font-synthesis: none;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  --bg-color: white;
  font-weight: 500;
}
body {
  font-family: Satoshi, system-ui, Avenir, Helvetica, Arial, sans-serif;
  background-color: var(--bg-color);
  margin: 0;
  display: flex;
  flex-direction: column;
  min-height: 100%;
}
button { all: unset; cursor: pointer; }
ul, li { all: unset; }
a { text-decoration: none; }
h1, h2, h3, h4, h5, h6, p { margin: 0; }
```

---

## Tech Stack Defaults

When scaffolding a new ScottyLabs web project:

1. **Framework:** Next.js (App Router) or Vite + React
2. **Styling:** CSS Modules with CSS custom properties (preferred) OR Tailwind CSS
3. **Fonts:** Satoshi (self-hosted or CDN) + JetBrains Mono (for code/decorative)
4. **Deployment:** Vercel (`npx vercel --yes` for CLI deploys)
5. **Build tool:** npm

## Tailwind Configuration (when using Tailwind)

```typescript
export default {
  theme: {
    extend: {
      fontFamily: {
        satoshi: ['Satoshi', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
        inter: ['Inter', 'sans-serif'],
      },
      colors: {
        black: {
          50:  'hsl(0, 0%, 97%)',
          100: 'hsl(0, 0%, 93%)',
          200: 'hsl(0, 0%, 89%)',
          300: 'hsl(0, 0%, 70%)',
          400: 'hsl(0, 0%, 50%)',
          500: 'hsl(0, 0%, 35%)',
          900: 'hsl(0, 0%, 0%)',
        },
        blue: {
          50:  'hsl(200, 23%, 97%)',
          300: 'hsl(230, 50%, 80%)',
          600: 'hsl(226, 76%, 50%)',
        },
        red: {
          500: 'hsl(0, 70%, 50%)',
        },
      },
      borderRadius: {
        base: '10px',
        lg: '40px',
      },
    },
  },
}
```
