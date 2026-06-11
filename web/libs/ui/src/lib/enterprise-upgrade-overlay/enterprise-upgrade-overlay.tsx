import { forwardRef, type ReactNode } from "react";

export interface EnterpriseUpgradeOverlayProps {
  /** Main title displayed in the overlay */
  title?: ReactNode;
  /** Description text or content explaining the feature */
  description?: ReactNode;
  /** Name of the feature being promoted (used in default text) */
  feature?: string;
  /** Optional URL for the "Learn more" button */
  learnMoreUrl?: string;
  /** Optional custom label for the primary CTA button */
  primaryButtonLabel?: string;
  /** Optional custom label for the secondary button */
  secondaryButtonLabel?: string;
  /** Whether to show the "Learn more" button */
  showLearnMore?: boolean;
  /** Callback when contact sales button is clicked */
  onContactSales?: () => void;
  /** Callback when learn more button is clicked */
  onLearnMore?: () => void;
  /** Callback to close/dismiss the overlay — renders a close button when provided */
  onClose?: () => void;
  /** Custom wrapper class name */
  className?: string;
  /** Test ID for testing */
  "data-testid"?: string;
}

// This fork ships every feature: there is no Enterprise tier to upsell, so the
// overlay renders nothing while keeping the component API for upstream call sites.
export const EnterpriseUpgradeOverlay = forwardRef<HTMLDivElement, EnterpriseUpgradeOverlayProps>(() => null);

EnterpriseUpgradeOverlay.displayName = "EnterpriseUpgradeOverlay";

export default EnterpriseUpgradeOverlay;
