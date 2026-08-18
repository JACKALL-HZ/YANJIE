/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        abyss: {
          DEFAULT: '#0B0F1A',
          2: '#0D1320',
        },
        surface: {
          1: '#141A2A',
          2: '#1A2234',
          3: '#222B40',
        },
        ink: {
          primary: '#E6EAF2',
          secondary: '#9AA6BC',
          muted: '#6B7689',
        },
        brand: {
          DEFAULT: '#4F8CFF',
          hover: '#6BA0FF',
        },
        cyan: {
          glow: '#22D3EE',
        },
        agent: {
          market: '#4F8CFF',
          env: '#34D399',
          personal: '#A78BFA',
          risk: '#F87171',
        },
      },
      fontFamily: {
        display: ['"Space Grotesk"', '"Noto Sans SC"', 'sans-serif'],
        sans: ['"Noto Sans SC"', '"PingFang SC"', '"Microsoft YaHei"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'Menlo', 'monospace'],
      },
      borderRadius: {
        chip: '999px',
        btn: '10px',
        card: '16px',
        modal: '20px',
      },
      transitionTimingFunction: {
        smooth: 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
      animation: {
        'fade-up': 'fadeUp 0.7s cubic-bezier(0.16,1,0.3,1) both',
        'pulse-soft': 'pulseSoft 2.4s ease-in-out infinite',
        shimmer: 'shimmer 1.8s linear infinite',
      },
      keyframes: {
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(24px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.45' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
    },
  },
  plugins: [],
}
