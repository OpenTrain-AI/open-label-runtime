import { NavLink } from "react-router-dom";
import { IconHotkeys } from "@humansignal/icons";
import { Button } from "@humansignal/ui";
import { openHotkeyHelp } from "@humansignal/app-common/pages/AccountSettings/sections/Hotkeys/Help";
import { useFixedLocation } from "../../providers/RoutesProvider";
import { cn } from "../../utils/bem";
import { FF_HOMEPAGE, isFF } from "../../utils/feature-flags";
import { LeftContextMenu, RightContextMenu } from "./ContextMenus";

const NAV_TABS = [
  isFF(FF_HOMEPAGE) && { label: "Home", to: "/", exact: true },
  { label: "Projects", to: "/projects" },
  { label: "Organization", to: "/organization" },
].filter(Boolean);

export function tabIsActive(tab, pathname) {
  const normalized = pathname.replace(/\/$/, "") || "/";
  if (tab.exact) return normalized === tab.to;
  return normalized === tab.to || normalized.startsWith(`${tab.to}/`);
}

/**
 * Top tab bar shown when the runtime is embedded in the OpenTrain app shell.
 * Row 1 replaces the standalone left sidebar with horizontal nav tabs that
 * match OpenTrain's job-page tab bars; row 2 keeps breadcrumbs and per-page
 * actions (e.g. the Create button on /projects).
 */
export const EmbedTopBar = () => {
  const location = useFixedLocation();
  const menubarClass = cn("menu-header");
  const contextItem = menubarClass.elem("context-item");

  return (
    <div className="sticky top-0 z-[1000] bg-neutral-background border-b border-neutral-border">
      <nav
        aria-label="Open Label"
        className="flex items-center gap-1 px-4 border-b border-neutral-border-subtle"
        data-testid="embed-top-bar-tabs"
      >
        {NAV_TABS.map((tab) => {
          const active = tabIsActive(tab, location.pathname);
          return (
            <NavLink
              key={tab.to}
              to={tab.to}
              exact={tab.exact}
              data-external
              aria-current={active ? "page" : undefined}
              className={[
                "px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors",
                active
                  ? "border-primary-border text-primary-content"
                  : "border-transparent text-neutral-content-subtler hover:text-neutral-content",
              ].join(" ")}
            >
              {tab.label}
            </NavLink>
          );
        })}
      </nav>
      <div className="flex items-center h-[var(--header-height)]">
        <div className={cn("menu-header").elem("context").toClassName()}>
          <LeftContextMenu className={contextItem.mod({ left: true }).toClassName()} />
          <RightContextMenu className={contextItem.mod({ right: true }).toClassName()} />
        </div>
        <div className={menubarClass.elem("hotkeys").toClassName()}>
          <div className={menubarClass.elem("hotkeys-button").toClassName()}>
            <Button
              variant="neutral"
              look="outlined"
              tooltip="Keyboard Shortcuts"
              data-testid="hotkeys-button"
              size="small"
              onClick={() => {
                openHotkeyHelp([
                  "annotation",
                  "data_manager",
                  "regions",
                  "tools",
                  "audio",
                  "video",
                  "timeseries",
                  "image_gallery",
                ]);
              }}
              icon={<IconHotkeys />}
            />
          </div>
        </div>
      </div>
    </div>
  );
};
