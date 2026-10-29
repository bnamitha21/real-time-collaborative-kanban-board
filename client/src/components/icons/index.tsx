import type { SVGProps } from "react";

export type IconProps = SVGProps<SVGSVGElement> & {
  size?: number;
};

const baseProps = (size = 16) => ({
  width: size,
  height: size,
  viewBox: "0 0 16 16",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.5,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
});

export function ArrowLeftIcon({ size = 16, ...props }: IconProps) {
  return (
    <svg {...baseProps(size)} {...props}>
      <path d="M10 3L5 8l5 5" />
    </svg>
  );
}

export function ArrowRightIcon({ size = 16, ...props }: IconProps) {
  return (
    <svg {...baseProps(size)} {...props}>
      <path d="M6 3l5 5-5 5" />
    </svg>
  );
}

export function UndoIcon({ size = 16, ...props }: IconProps) {
  return (
    <svg {...baseProps(size)} {...props}>
      <path d="M3 6h7a3.5 3.5 0 0 1 0 7H8" />
      <path d="M5.5 3.5L3 6l2.5 2.5" />
    </svg>
  );
}

export function RedoIcon({ size = 16, ...props }: IconProps) {
  return (
    <svg {...baseProps(size)} {...props}>
      <path d="M13 6H6a3.5 3.5 0 0 0 0 7h2" />
      <path d="M10.5 3.5L13 6l-2.5 2.5" />
    </svg>
  );
}

export function PlusIcon({ size = 16, ...props }: IconProps) {
  return (
    <svg {...baseProps(size)} {...props}>
      <path d="M8 3v10M3 8h10" />
    </svg>
  );
}

export function CloseIcon({ size = 16, ...props }: IconProps) {
  return (
    <svg {...baseProps(size)} {...props}>
      <path d="M4 4l8 8M12 4L4 12" />
    </svg>
  );
}

export function ClockIcon({ size = 16, ...props }: IconProps) {
  return (
    <svg {...baseProps(size)} {...props}>
      <circle cx="8" cy="8" r="6" />
      <path d="M8 5v3.5l2 1" />
    </svg>
  );
}

export function CheckIcon({ size = 16, ...props }: IconProps) {
  return (
    <svg {...baseProps(size)} {...props}>
      <path d="M3.5 8.5l3 3 6-6" />
    </svg>
  );
}

export function UserIcon({ size = 16, ...props }: IconProps) {
  return (
    <svg {...baseProps(size)} {...props}>
      <circle cx="8" cy="5" r="2.5" />
      <path d="M3.5 13.5c0-2.2 2-3.5 4.5-3.5s4.5 1.3 4.5 3.5" />
    </svg>
  );
}

export function BuildingIcon({ size = 16, ...props }: IconProps) {
  return (
    <svg {...baseProps(size)} {...props}>
      <path d="M3 14V3a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v11M2 14h12M5 5h2M9 5h2M5 8h2M9 8h2M7 14v-3h2v3" />
    </svg>
  );
}

export function BranchIcon({ size = 16, ...props }: IconProps) {
  return (
    <svg {...baseProps(size)} {...props}>
      <circle cx="4" cy="4" r="1.5" />
      <circle cx="4" cy="12" r="1.5" />
      <circle cx="12" cy="7" r="1.5" />
      <path d="M4 5.5v5M4 8a4 4 0 0 1 4-4h2.5" />
    </svg>
  );
}

export function AlertIcon({ size = 16, ...props }: IconProps) {
  return (
    <svg {...baseProps(size)} {...props}>
      <path d="M8 2.5l5.5 10H2.5L8 2.5z" />
      <path d="M8 6.5v3M8 11.5h.01" />
    </svg>
  );
}

export function WifiOffIcon({ size = 16, ...props }: IconProps) {
  return (
    <svg {...baseProps(size)} {...props}>
      <path d="M2 2l12 12M5.5 5.8a7 7 0 0 1 5 0M3.5 3.5A11 11 0 0 1 14 6M7 9a3 3 0 0 1 2 0M8 12.5h.01" />
    </svg>
  );
}

export function DotsIcon({ size = 16, ...props }: IconProps) {
  return (
    <svg {...baseProps(size)} {...props}>
      <circle cx="4" cy="8" r="1" fill="currentColor" stroke="none" />
      <circle cx="8" cy="8" r="1" fill="currentColor" stroke="none" />
      <circle cx="12" cy="8" r="1" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function TrashIcon({ size = 16, ...props }: IconProps) {
  return (
    <svg {...baseProps(size)} {...props}>
      <path d="M3 4h10M6 4V2.5A.5.5 0 0 1 6.5 2h3a.5.5 0 0 1 .5.5V4M4.5 4l.8 9.2a1 1 0 0 0 1 .8h3.4a1 1 0 0 0 1-.8L11.5 4" />
      <path d="M7 7v4M9 7v4" />
    </svg>
  );
}

export function ChevronDownIcon({ size = 16, ...props }: IconProps) {
  return (
    <svg {...baseProps(size)} {...props}>
      <path d="M4 6l4 4 4-4" />
    </svg>
  );
}

