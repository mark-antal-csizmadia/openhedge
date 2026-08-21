export const BRAND_CANVAS = "#0c1612";
export const BRAND_MARK_FIELD = "#0f3d2e";
export const BRAND_MINT = "#7dcea0";
export const BRAND_CREAM = "#f4e3c1";

const MARK_VIEWBOX = 128;

export function BrandMark({ size }: { size: number }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox={`0 0 ${MARK_VIEWBOX} ${MARK_VIEWBOX}`}
    >
      <rect width={MARK_VIEWBOX} height={MARK_VIEWBOX} rx="28" fill={BRAND_MARK_FIELD} />
      <path
        fill={BRAND_MINT}
        d="M24 92h12v-28h-12zm20 0h12V36H44zm20 0h12V52H64zm20 0h12V28H84zm20 0h12V60h-12z"
      />
      <path
        fill="none"
        stroke={BRAND_CREAM}
        strokeWidth="6"
        strokeLinecap="round"
        d="M28 84l18-22 16 10 22-32 16 14"
      />
    </svg>
  );
}
