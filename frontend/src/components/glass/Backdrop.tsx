/**
 * The sunlit room behind every glass surface (the reference puts its dashboard over a bright interior).
 * Drawn as one static SVG: no photo to download, sharp at any size, and the glass does the blurring.
 */
export function Backdrop() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-parchment">
      <svg className="h-full w-full" viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice">
        <defs>
          <linearGradient id="bd-wall" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#f4f2ee" />
            <stop offset="1" stopColor="#e6e2da" />
          </linearGradient>
          <linearGradient id="bd-sky" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#d9e4ee" />
            <stop offset="0.62" stopColor="#eef1ef" />
            <stop offset="1" stopColor="#f7f5f0" />
          </linearGradient>
          <linearGradient id="bd-floor" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#e4d9ca" />
            <stop offset="1" stopColor="#d3c4b0" />
          </linearGradient>
          <linearGradient id="bd-beam" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#ffffff" stopOpacity="0.55" />
            <stop offset="1" stopColor="#ffffff" stopOpacity="0" />
          </linearGradient>
          <radialGradient id="bd-glow" cx="0.5" cy="0.35" r="0.6">
            <stop offset="0" stopColor="#fffdf8" stopOpacity="0.9" />
            <stop offset="1" stopColor="#fffdf8" stopOpacity="0" />
          </radialGradient>
          <filter id="bd-soft" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="14" />
          </filter>
          <filter id="bd-leaf" x="-10%" y="-10%" width="120%" height="120%">
            <feGaussianBlur stdDeviation="0.8" />
          </filter>
        </defs>

        <rect width="1600" height="1000" fill="url(#bd-wall)" />

        {/* Tall windows: sky, a hint of trees outside, white frames */}
        <g>
          <rect x="330" y="70" width="940" height="650" rx="6" fill="#e9e6e0" />
          <rect x="344" y="84" width="912" height="622" fill="url(#bd-sky)" />
          <g filter="url(#bd-soft)" opacity="0.55">
            <ellipse cx="470" cy="660" rx="170" ry="90" fill="#aebfa6" />
            <ellipse cx="760" cy="690" rx="220" ry="80" fill="#b8c8b0" />
            <ellipse cx="1110" cy="650" rx="190" ry="110" fill="#a9bba2" />
          </g>
          <g fill="#fbfaf7">
            <rect x="330" y="70" width="940" height="16" />
            <rect x="330" y="704" width="940" height="18" />
            <rect x="330" y="70" width="16" height="652" />
            <rect x="1254" y="70" width="16" height="652" />
            <rect x="639" y="70" width="12" height="652" />
            <rect x="949" y="70" width="12" height="652" />
            <rect x="330" y="262" width="940" height="10" />
          </g>
        </g>

        {/* Pendant lamp */}
        <line x1="800" y1="0" x2="800" y2="118" stroke="#2a2a2d" strokeWidth="2" />
        <path d="M758 150 Q800 104 842 150 Z" fill="#2a2a2d" />
        <ellipse cx="800" cy="151" rx="42" ry="4" fill="#3a3a3e" />

        {/* Floor with the windows' light lying on it */}
        <rect x="0" y="722" width="1600" height="278" fill="url(#bd-floor)" />
        <g stroke="#000" strokeOpacity="0.035" strokeWidth="2">
          <line x1="0" y1="790" x2="1600" y2="790" />
          <line x1="0" y1="870" x2="1600" y2="870" />
          <line x1="0" y1="955" x2="1600" y2="955" />
        </g>
        <g filter="url(#bd-soft)">
          <polygon points="344,722 639,722 560,1000 150,1000" fill="url(#bd-beam)" />
          <polygon points="651,722 949,722 930,1000 600,1000" fill="url(#bd-beam)" />
          <polygon points="961,722 1256,722 1380,1000 980,1000" fill="url(#bd-beam)" />
        </g>
        <rect width="1600" height="1000" fill="url(#bd-glow)" />

        {/* Plant on the left */}
        <g filter="url(#bd-leaf)">
          <g fill="#6f8c67">
            <ellipse cx="170" cy="520" rx="34" ry="92" transform="rotate(-28 170 520)" />
            <ellipse cx="236" cy="500" rx="30" ry="98" transform="rotate(12 236 500)" />
            <ellipse cx="120" cy="590" rx="28" ry="80" transform="rotate(-52 120 590)" />
          </g>
          <g fill="#88a37f">
            <ellipse cx="206" cy="560" rx="30" ry="86" transform="rotate(-8 206 560)" />
            <ellipse cx="268" cy="585" rx="26" ry="74" transform="rotate(38 268 585)" />
            <ellipse cx="150" cy="620" rx="24" ry="66" transform="rotate(-70 150 620)" />
          </g>
        </g>
        <path d="M140 660 H280 L268 780 H152 Z" fill="#d6cec2" />
        <rect x="136" y="652" width="148" height="14" rx="4" fill="#e1dad0" />

        {/* Sofa on the right */}
        <ellipse cx="1360" cy="838" rx="300" ry="36" fill="#000" opacity="0.06" />
        <rect x="1150" y="640" width="420" height="120" rx="34" fill="#dcd9d4" />
        <rect x="1180" y="700" width="360" height="98" rx="26" fill="#e6e3de" />
        <rect x="1128" y="690" width="66" height="116" rx="28" fill="#d4d0ca" />
        <rect x="1526" y="690" width="66" height="116" rx="28" fill="#d4d0ca" />
        <rect x="1180" y="806" width="10" height="26" rx="3" fill="#8f877c" />
        <rect x="1530" y="806" width="10" height="26" rx="3" fill="#8f877c" />
      </svg>
    </div>
  );
}
