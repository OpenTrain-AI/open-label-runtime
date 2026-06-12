import { fireEvent, render, screen } from "@testing-library/react";

jest.mock("@humansignal/ui", () => ({
  // eslint-disable-next-line react/prop-types
  Button: ({ look, ...props }) => <button {...props} />,
}));
jest.mock("../../components/Form", () => ({ Form: () => null, Input: () => null, TextArea: () => null }));
jest.mock("../../components/Form/Elements/RadioGroup/RadioGroup", () => ({ RadioGroup: () => null }));
jest.mock("../../providers/ProjectProvider", () => ({
  ProjectContext: require("react").createContext({ project: {}, fetchProject: () => {} }),
}));
jest.mock("../../utils/embed", () => ({
  isEmbedded: jest.fn(),
  notifyEmbedParent: jest.fn(),
  onEmbedParentMessage: jest.fn(() => () => {}),
}));

const { isEmbedded, notifyEmbedParent, onEmbedParentMessage } = require("../../utils/embed");
const { OpenTrainJobSection } = require("./GeneralSettings");

describe("OpenTrainJobSection", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    onEmbedParentMessage.mockImplementation(() => () => {});
  });

  it("shows the linked job with its mode and no assign button", () => {
    isEmbedded.mockReturnValue(true);
    render(
      <OpenTrainJobSection
        project={{ id: 7, title: "P", opentrain_job: { jobId: "job-1", jobTitle: "Image QA", mode: "production" } }}
        fetchProject={jest.fn()}
      />,
    );

    expect(screen.getByTestId("opentrain-section").textContent).toContain(
      "Linked to job Image QA — Production labeling",
    );
    expect(screen.queryByLabelText("Assign to OpenTrain job")).toBeNull();
  });

  it("shows not-linked state with an assign button in embed mode that posts assign-to-job", () => {
    isEmbedded.mockReturnValue(true);
    render(<OpenTrainJobSection project={{ id: 7, title: "P", opentrain_job: null }} fetchProject={jest.fn()} />);

    expect(screen.getByTestId("opentrain-section").textContent).toContain("Not linked to an OpenTrain job.");
    fireEvent.click(screen.getByLabelText("Assign to OpenTrain job"));
    expect(notifyEmbedParent).toHaveBeenCalledWith({ type: "open-label:assign-to-job", projectId: 7, title: "P" });
  });

  it("hides the assign button outside embed mode", () => {
    isEmbedded.mockReturnValue(false);
    render(<OpenTrainJobSection project={{ id: 7, title: "P", opentrain_job: null }} fetchProject={jest.fn()} />);

    expect(screen.getByTestId("opentrain-section").textContent).toContain("Not linked to an OpenTrain job.");
    expect(screen.queryByLabelText("Assign to OpenTrain job")).toBeNull();
  });

  it("refetches the project when the parent reports a job-link update for this project", () => {
    isEmbedded.mockReturnValue(true);
    let captured;
    onEmbedParentMessage.mockImplementation((type, handler) => {
      captured = { type, handler };
      return () => {};
    });
    const fetchProject = jest.fn();
    render(<OpenTrainJobSection project={{ id: 7, title: "P", opentrain_job: null }} fetchProject={fetchProject} />);

    expect(captured.type).toBe("open-label:job-link-updated");
    captured.handler({ type: "open-label:job-link-updated", projectId: "7" });
    expect(fetchProject).toHaveBeenCalledWith(7, true);

    captured.handler({ type: "open-label:job-link-updated", projectId: "8" });
    expect(fetchProject).toHaveBeenCalledTimes(1);
  });
});
