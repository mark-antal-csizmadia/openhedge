export function Mark({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 128 128"
      className={className}
      aria-hidden="true"
    >
      <rect width="128" height="128" rx="28" fill="#0f3d2e" />
      <path
        fill="#7dcea0"
        d="M24 92h12v-28h-12zm20 0h12V36H44zm20 0h12V52H64zm20 0h12V28H84zm20 0h12V60h-12z"
      />
      <path
        fill="none"
        stroke="#f4e3c1"
        strokeWidth="6"
        strokeLinecap="round"
        d="M28 84l18-22 16 10 22-32 16 14"
      />
    </svg>
  );
}
