import { forwardRef } from "react";
import type { BadgeProps } from "../badge/badge";

export type EnterpriseBadgeProps = Omit<BadgeProps, "variant" | "icon"> & {
  /** Icon to show. Defaults to IconSpark. Pass null for text-only (no icon). */
  icon?: React.ReactNode | null;
};

// This fork ships every feature: there is no Enterprise tier, so the badge
// renders nothing while keeping the component API for upstream call sites.
export const EnterpriseBadge = forwardRef<HTMLDivElement, EnterpriseBadgeProps>(() => null);

EnterpriseBadge.displayName = "EnterpriseBadge";
