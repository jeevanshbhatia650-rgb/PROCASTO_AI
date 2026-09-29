import type { ReactNode, SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function Icon({ size = 18, children, ...rest }: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {children}
    </svg>
  );
}

export const MicIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
  </Icon>
);
export const PlayIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M8 5.5v13l10.5-6.5z" fill="currentColor" stroke="none" />
  </Icon>
);
const WasherIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="4" y="3" width="16" height="18" rx="3" />
    <circle cx="12" cy="13" r="4.5" />
    <path d="M7.5 6.5h2" />
  </Icon>
);
const DryerIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="4" y="3" width="16" height="18" rx="3" />
    <circle cx="12" cy="13" r="4.5" />
    <path d="M10.5 12c.8-.6 2.2-.6 3 0" />
    <path d="M7.5 6.5h2M14.5 6.5h2" />
  </Icon>
);
const AcIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="3" y="4" width="18" height="8" rx="2.5" />
    <path d="M7 16c0 1.5-1 2.2-1 3.5M12 16v4M17 16c0 1.5 1 2.2 1 3.5" />
  </Icon>
);
export const BookIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5z" />
    <path d="M5 19.5A1.5 1.5 0 0 0 6.5 21H19" />
  </Icon>
);
export const ChatIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M5 5h14v10H10l-4 3.5V15H5z" />
  </Icon>
);
export const SpeakerIcon = ({ muted, ...p }: IconProps & { muted?: boolean }) => (
  <Icon {...p}>
    <path d="M4 9.5h3.5L12 6v12l-4.5-3.5H4z" />
    {muted ? <path d="M16 9.5l5 5M21 9.5l-5 5" /> : <path d="M16 9a4 4 0 0 1 0 6M18.5 6.5a7.5 7.5 0 0 1 0 11" />}
  </Icon>
);
export const PauseIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M9 6v12M15 6v12" />
  </Icon>
);
export const KeyboardIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="3" y="6" width="18" height="12" rx="2.5" />
    <path d="M7 10h.01M11 10h.01M15 10h.01M8 14h8" />
  </Icon>
);

export function DeviceIcon({ kind, ...p }: IconProps & { kind: string }) {
  if (kind === "washer") return <WasherIcon {...p} />;
  if (kind === "dryer") return <DryerIcon {...p} />;
  return <AcIcon {...p} />;
}

/** The PROCASTO mark: a pulse line (original artwork). */
export const LogoMark = ({ size = 18 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
    <rect width="32" height="32" rx="8" fill="#1d1d1f" />
    <path d="M5 17h5l3-7 4 13 3-9 2 3h5" fill="none" stroke="#2997ff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
