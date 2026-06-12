jest.mock("react-router-dom", () => ({ NavLink: () => null }));
jest.mock("@humansignal/ui", () => ({ Button: () => null }));
jest.mock("@humansignal/icons", () => ({ IconHotkeys: () => null }));
jest.mock("@humansignal/app-common/pages/AccountSettings/sections/Hotkeys/Help", () => ({
  openHotkeyHelp: jest.fn(),
}));
jest.mock("../../providers/RoutesProvider", () => ({ useFixedLocation: jest.fn() }));
jest.mock("./ContextMenus", () => ({ LeftContextMenu: () => null, RightContextMenu: () => null }));

window.APP_SETTINGS = window.APP_SETTINGS ?? {};

const { tabIsActive } = require("./EmbedTopBar");

const HOME = { label: "Home", to: "/", exact: true };
const PROJECTS = { label: "Projects", to: "/projects" };
const ORGANIZATION = { label: "Organization", to: "/organization" };

describe("EmbedTopBar tabIsActive", () => {
  it("matches Home only on the exact root path", () => {
    expect(tabIsActive(HOME, "/")).toBe(true);
    expect(tabIsActive(HOME, "/projects")).toBe(false);
    expect(tabIsActive(HOME, "/organization")).toBe(false);
  });

  it("matches Projects on the list and nested project pages", () => {
    expect(tabIsActive(PROJECTS, "/projects")).toBe(true);
    expect(tabIsActive(PROJECTS, "/projects/")).toBe(true);
    expect(tabIsActive(PROJECTS, "/projects/12/data")).toBe(true);
    expect(tabIsActive(PROJECTS, "/projects/12/settings/labeling")).toBe(true);
    expect(tabIsActive(PROJECTS, "/")).toBe(false);
    expect(tabIsActive(PROJECTS, "/organization")).toBe(false);
  });

  it("does not treat sibling prefixes as active", () => {
    expect(tabIsActive(PROJECTS, "/projects-archive")).toBe(false);
    expect(tabIsActive(ORGANIZATION, "/organizations")).toBe(false);
  });

  it("matches Organization on the page and its subpaths", () => {
    expect(tabIsActive(ORGANIZATION, "/organization")).toBe(true);
    expect(tabIsActive(ORGANIZATION, "/organization/")).toBe(true);
    expect(tabIsActive(ORGANIZATION, "/projects")).toBe(false);
  });
});
