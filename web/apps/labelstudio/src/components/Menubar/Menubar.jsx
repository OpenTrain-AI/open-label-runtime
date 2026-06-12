import { createContext, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  IconBook,
  IconFolder,
  IconHome,
  IconHotkeys,
  IconPeople,
  IconPersonInCircle,
  IconPin,
  IconTerminal,
  IconDoor,
} from "@humansignal/icons";
import { LSLogo } from "../../assets/images";
import { Button, Userpic, ThemeToggle } from "@humansignal/ui";
import { useFixedLocation } from "../../providers/RoutesProvider";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { displayableEmail, userDisplayName } from "@humansignal/core";
import { cn } from "../../utils/bem";
import { absoluteURL, isDefined } from "../../utils/helpers";
import { Dropdown } from "@humansignal/ui";
import { Hamburger } from "../Hamburger/Hamburger";
import { Menu } from "../Menu/Menu";
import { VersionNotifier, VersionProvider } from "../VersionNotifier/VersionNotifier";
import "./Menubar.prefix.css";
import "./MenuContent.prefix.css";
import "./MenuSidebar.prefix.css";
import { FF_HOMEPAGE } from "../../utils/feature-flags";
import { pages } from "@humansignal/app-common";
import { isFF } from "../../utils/feature-flags";
import { ff } from "@humansignal/core";
import { openHotkeyHelp } from "@humansignal/app-common/pages/AccountSettings/sections/Hotkeys/Help";
import { LeftContextMenu, RightContextMenu } from "./ContextMenus";
import { EmbedTopBar } from "./EmbedTopBar";

export const MenubarContext = createContext();

export const Menubar = ({
  enabled,
  embedded = false,
  defaultOpened,
  defaultPinned,
  children,
  onSidebarToggle,
  onSidebarPin,
}) => {
  const menuDropdownRef = useRef();
  const useMenuRef = useRef();
  const { user, isLoading } = useAuth();
  const location = useFixedLocation();

  const [sidebarOpened, setSidebarOpened] = useState(defaultOpened ?? false);
  const [sidebarPinned, setSidebarPinned] = useState(defaultPinned ?? false);
  const [PageContext, setPageContext] = useState({
    Component: null,
    props: {},
  });

  const menubarClass = cn("menu-header");
  const menubarContext = menubarClass.elem("context");
  const sidebarClass = cn("sidebar");
  const contentClass = cn("content-wrapper");
  const contextItem = menubarClass.elem("context-item");
  const showNewsletterDot = !isDefined(user?.allow_newsletters);

  const sidebarPin = useCallback(
    (e) => {
      e.preventDefault();

      const newState = !sidebarPinned;

      setSidebarPinned(newState);
      onSidebarPin?.(newState);
    },
    [sidebarPinned],
  );

  const sidebarToggle = useCallback(
    (visible) => {
      const newState = visible;

      setSidebarOpened(newState);
      onSidebarToggle?.(newState);
    },
    [sidebarOpened],
  );

  const providerValue = useMemo(
    () => ({
      PageContext,

      setContext(ctx) {
        setTimeout(() => {
          setPageContext({
            ...PageContext,
            Component: ctx,
          });
        });
      },

      setProps(props) {
        setTimeout(() => {
          setPageContext({
            ...PageContext,
            props,
          });
        });
      },

      contextIsSet(ctx) {
        return PageContext.Component === ctx;
      },
    }),
    [PageContext],
  );

  useEffect(() => {
    if (!sidebarPinned) {
      menuDropdownRef?.current?.close();
    }
    useMenuRef?.current?.close();
  }, [location]);

  // Embedded mode (OpenTrain shell iframe): the runtime renders the full app
  // with a top tab bar (Home / Projects / Organization) plus breadcrumbs and
  // per-page actions — no logo, sidebar, or account chrome; the shell owns those.
  return (
    <div className={contentClass}>
      {embedded ? (
        <EmbedTopBar />
      ) : (
        enabled && (
          <div className={menubarClass.toClassName()}>
            <Dropdown.Trigger dropdown={menuDropdownRef} closeOnClickOutside={!sidebarPinned}>
              <div className={`${menubarClass.elem("trigger")} main-menu-trigger`}>
                <LSLogo className={`${menubarClass.elem("logo")}`} alt="Open Label logo" />
                <Hamburger opened={sidebarOpened} />
              </div>
            </Dropdown.Trigger>

            <div className={menubarContext}>
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

            {ff.isActive(ff.FF_THEME_TOGGLE) && <ThemeToggle />}

            <Dropdown.Trigger
              ref={useMenuRef}
              align="right"
              content={
                <Menu>
                  <Menu.Item
                    icon={<IconPersonInCircle />}
                    label="Account &amp; Settings"
                    href={pages.AccountSettingsPage.path}
                  />
                  {/* <Menu.Item label="Dark Mode"/> */}
                  <Menu.Item icon={<IconDoor />} label="Log Out" href={absoluteURL("/logout")} data-external />
                  {showNewsletterDot && (
                    <>
                      <Menu.Divider />
                      <Menu.Item
                        className={cn("newsletter-menu-item").toClassName()}
                        href={pages.AccountSettingsPage.path}
                      >
                        <span>Please check new notification settings in the Account & Settings page</span>
                        <span className={cn("newsletter-menu-badge").toClassName()} />
                      </Menu.Item>
                    </>
                  )}
                </Menu>
              }
            >
              <div
                title={displayableEmail(user?.email) || userDisplayName(user)}
                className={menubarClass.elem("user").toClassName()}
              >
                <Userpic user={user} isInProgress={isLoading} />
                {showNewsletterDot && <div className={menubarClass.elem("userpic-badge").toClassName()} />}
              </div>
            </Dropdown.Trigger>
          </div>
        )
      )}

      <VersionProvider>
        <div className={contentClass.elem("body").toClassName()}>
          {enabled && !embedded && (
            <Dropdown
              ref={menuDropdownRef}
              onToggle={sidebarToggle}
              onVisibilityChanged={() => window.dispatchEvent(new Event("resize"))}
              visible={sidebarOpened}
              className={[sidebarClass, sidebarClass.mod({ floating: !sidebarPinned })].join(" ")}
              style={{ width: 240 }}
            >
              <Menu>
                {isFF(FF_HOMEPAGE) && <Menu.Item label="Home" to="/" icon={<IconHome />} data-external exact />}
                <Menu.Item label="Projects" to="/projects" icon={<IconFolder />} data-external exact />
                <Menu.Item label="Organization" to="/organization" icon={<IconPeople />} data-external exact />

                <Menu.Spacer />

                <Menu.Item
                  label="OpenTrain App"
                  href="https://app.opentrain.ai"
                  icon={<IconTerminal />}
                  target="_blank"
                />
                <Menu.Item
                  label="Contact Support"
                  href="mailto:support@opentrain.ai"
                  icon={<IconBook />}
                  target="_blank"
                />

                <VersionNotifier showCurrentVersion />

                <Menu.Divider />

                <Menu.Item
                  icon={<IconPin />}
                  className={sidebarClass.elem("pin").toClassName()}
                  onClick={sidebarPin}
                  active={sidebarPinned}
                >
                  {sidebarPinned ? "Unpin menu" : "Pin menu"}
                </Menu.Item>
              </Menu>
            </Dropdown>
          )}

          <MenubarContext.Provider value={providerValue}>
            <div
              className={contentClass
                .elem("content")
                .mod({ withSidebar: sidebarPinned && sidebarOpened })
                .toClassName()}
            >
              {children}
            </div>
          </MenubarContext.Provider>
        </div>
      </VersionProvider>
    </div>
  );
};
