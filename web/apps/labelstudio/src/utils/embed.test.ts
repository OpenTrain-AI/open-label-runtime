import { notifyEmbedParent } from "./embed";

const EMBED_KEY = "open_label_embed";
const EMBED_ORIGIN_KEY = "open_label_embed_origin";
const PARENT_ORIGIN = "https://app.opentrain.test";

describe("notifyEmbedParent", () => {
  let postMessage: jest.Mock;

  beforeEach(() => {
    postMessage = jest.fn();
    Object.defineProperty(window, "parent", {
      configurable: true,
      value: { postMessage },
    });
    window.sessionStorage.clear();
  });

  afterEach(() => {
    Object.defineProperty(window, "parent", { configurable: true, value: window });
  });

  it("posts the assign-to-job payload to the embedding origin", () => {
    window.sessionStorage.setItem(EMBED_KEY, "1");
    window.sessionStorage.setItem(EMBED_ORIGIN_KEY, PARENT_ORIGIN);

    notifyEmbedParent({ type: "open-label:assign-to-job", projectId: 42, title: "Street Scenes" });

    expect(postMessage).toHaveBeenCalledTimes(1);
    expect(postMessage).toHaveBeenCalledWith(
      { type: "open-label:assign-to-job", projectId: 42, title: "Street Scenes" },
      PARENT_ORIGIN,
    );
  });

  it("posts the open-team message", () => {
    window.sessionStorage.setItem(EMBED_KEY, "1");
    window.sessionStorage.setItem(EMBED_ORIGIN_KEY, PARENT_ORIGIN);

    notifyEmbedParent({ type: "open-label:open-team" });

    expect(postMessage).toHaveBeenCalledWith({ type: "open-label:open-team" }, PARENT_ORIGIN);
  });

  it("is a no-op outside embed mode", () => {
    notifyEmbedParent({ type: "open-label:assign-to-job", projectId: 42, title: "Street Scenes" });
    expect(postMessage).not.toHaveBeenCalled();
  });

  it("is a no-op when no embed origin was provided", () => {
    window.sessionStorage.setItem(EMBED_KEY, "1");
    notifyEmbedParent({ type: "open-label:open-team" });
    expect(postMessage).not.toHaveBeenCalled();
  });
});
