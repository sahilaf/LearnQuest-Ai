/** @type {import('tailwindcss').Config} */
// SHARED FILE - change by agreement (plan.md 2.4). Design tokens: plan.md 4.5.
//
// LearnQuest is a dark-first product surface: a near-black canvas, panels lifted
// by one hairline border, an editorial serif for display type against a neutral
// UI face, and exactly one accent colour. Full rules: docs/DESIGN_GUIDELINES.md
//
// Why every colour is a CSS variable
// ----------------------------------
// The previous system hard-coded dark values inline (`dark:bg-[#171C23]`) in
// about forty places with no token behind them, so nothing matched anything and
// a palette change meant a find-and-replace across the app. Colours now resolve
// through `rgb(var(--x) / <alpha-value>)`, which keeps Tailwind's opacity
// modifiers working (`bg-easy/15`, `border-line/60`) while letting the whole
// theme swap from one place in index.css.
const token = (name) => `rgb(var(${name}) / <alpha-value>)`;

export default {
  // Dark is the default theme, applied on :root. `.light` opts back out, so the
  // class strategy stays available without `dark:` prefixes everywhere.
  darkMode: ['class', '.dark'],
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Brand. Primary actions, active navigation and focus rings. Never
        // decoration - if it is violet, it is interactive or it is the tutor.
        primary: {
          50: token('--primary-50'),
          100: token('--primary-100'),
          200: token('--primary-200'),
          300: token('--primary-300'),
          400: token('--primary-400'),
          500: token('--primary-500'),
          600: token('--primary-600'),
          700: token('--primary-700'),
          800: token('--primary-800'),
          900: token('--primary-900'),
        },

        // Difficulty and status. The only other colours allowed to carry
        // meaning, mapped 1:1 to the words a user reads.
        easy: {
          DEFAULT: token('--easy'),
          bg: token('--easy-bg'),
          fg: token('--easy-fg'),
        },
        medium: {
          DEFAULT: token('--medium'),
          bg: token('--medium-bg'),
          fg: token('--medium-fg'),
        },
        hard: {
          DEFAULT: token('--hard'),
          bg: token('--hard-bg'),
          fg: token('--hard-fg'),
        },
        info: {
          DEFAULT: token('--info'),
          bg: token('--info-bg'),
          fg: token('--info-fg'),
        },

        // Neutral ramp. `canvas` is the page, `surface` is a panel on it, and
        // `raised` is a panel on a panel - three levels, no more.
        ink: token('--ink'), // headings
        body: token('--body'), // body copy
        muted: token('--muted'), // secondary text, table headers
        faint: token('--faint'), // placeholders, disabled
        line: token('--line'), // 1px hairline
        'line-strong': token('--line-strong'), // input borders, real dividers
        surface: token('--surface'), // cards, tables, panels
        raised: token('--raised'), // menus, popovers, nested panels
        canvas: token('--canvas'), // page background
      },

      fontFamily: {
        // Display is editorial, UI is neutral. Mixing a high-contrast serif with
        // a workhorse sans is what keeps this from looking like a dashboard
        // template; the serif is for page titles and hero copy only.
        display: ['"Instrument Serif"', 'Georgia', 'ui-serif', 'serif'],
        sans: ['Inter', 'Roboto', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },

      fontSize: {
        // 15px body. The old scale bottomed out at 11px for chips and 13px for
        // navigation, which is below what anyone should be asked to read on a
        // laptop at arm's length.
        '2xs': ['12px', { lineHeight: '16px' }],
        xs: ['13px', { lineHeight: '18px' }],
        sm: ['14px', { lineHeight: '20px' }],
        base: ['15px', { lineHeight: '24px' }],
        lg: ['17px', { lineHeight: '26px' }],
        xl: ['20px', { lineHeight: '28px' }],
        '2xl': ['24px', { lineHeight: '32px' }],
        '3xl': ['30px', { lineHeight: '38px' }],
        '4xl': ['40px', { lineHeight: '46px', letterSpacing: '-0.01em' }],
        '5xl': ['56px', { lineHeight: '58px', letterSpacing: '-0.02em' }],
        '6xl': ['72px', { lineHeight: '72px', letterSpacing: '-0.02em' }],
      },

      maxWidth: {
        // The app shell. 1400px left ~260px of dead margin each side at 1920
        // while the gutter inside was only 16px - cramped and empty at once.
        shell: '1600px',
        // Anything the eye reads as prose stays inside a comfortable measure,
        // regardless of how wide the shell gets.
        prose: '68ch',
      },

      borderRadius: {
        // Sharp. Depth comes from a border and a level change, not from
        // rounding everything into a pill.
        DEFAULT: '6px',
        md: '6px',
        lg: '8px',
        xl: '12px',
        '2xl': '16px',
        pill: '9999px', // status chips and avatars only
      },

      boxShadow: {
        // On a near-black canvas a drop shadow is nearly invisible, so lift
        // comes from the border. These are only for things that truly float.
        dropdown: '0 8px 24px rgba(0, 0, 0, 0.45)',
        modal: '0 24px 64px rgba(0, 0, 0, 0.55)',
        // A violet glow reserved for the primary action and the live avatar.
        glow: '0 0 0 1px rgb(var(--primary-500) / 0.25), 0 8px 32px rgb(var(--primary-600) / 0.25)',
      },

      keyframes: {
        'fade-in': { '0%': { opacity: 0 }, '100%': { opacity: 1 } },
        'rise-in': {
          '0%': { opacity: 0, transform: 'translateY(4px)' },
          '100%': { opacity: 1, transform: 'translateY(0)' },
        },
        shimmer: { '100%': { transform: 'translateX(100%)' } },
      },
      animation: {
        'fade-in': 'fade-in 0.15s ease-out',
        'rise-in': 'rise-in 0.2s ease-out',
        shimmer: 'shimmer 1.4s infinite',
      },
    },
  },
  plugins: [],
};
