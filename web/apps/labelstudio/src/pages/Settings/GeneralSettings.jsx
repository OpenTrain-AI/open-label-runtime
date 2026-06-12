import { Button } from "@humansignal/ui";
import { useCallback, useContext, useEffect } from "react";
import { Form, Input, TextArea } from "../../components/Form";
import { RadioGroup } from "../../components/Form/Elements/RadioGroup/RadioGroup";
import { ProjectContext } from "../../providers/ProjectProvider";
import { cn } from "../../utils/bem";
import { isEmbedded, notifyEmbedParent, onEmbedParentMessage } from "../../utils/embed";

const JOB_LINK_MODE_LABELS = {
  screening: "Screening assessment",
  production: "Production labeling",
};

export const OpenTrainJobSection = ({ project, fetchProject }) => {
  useEffect(() => {
    if (!project.id) return undefined;
    return onEmbedParentMessage("open-label:job-link-updated", (data) => {
      if (String(data.projectId) === String(project.id)) fetchProject(project.id, true);
    });
  }, [project.id, fetchProject]);

  const job = project.opentrain_job;

  return (
    <div className={cn("settings-wrapper").toClassName()} style={{ marginTop: 32 }} data-testid="opentrain-section">
      <div className={cn("settings-wrapper").elem("header").toClassName()}>OpenTrain</div>
      <div className="settings-description">
        {job ? (
          <p style={{ margin: 0 }}>
            Linked to job <b>{job.jobTitle ?? job.jobId}</b>
            {job.mode ? ` — ${JOB_LINK_MODE_LABELS[job.mode] ?? job.mode}` : ""}
          </p>
        ) : (
          <p style={{ margin: 0 }}>Not linked to an OpenTrain job.</p>
        )}
      </div>
      {isEmbedded() && !job && (
        <div style={{ marginTop: 16 }}>
          <Button
            type="button"
            look="outlined"
            aria-label="Assign to OpenTrain job"
            onClick={() =>
              notifyEmbedParent({
                type: "open-label:assign-to-job",
                projectId: project.id,
                title: project.title ?? "New project",
              })
            }
          >
            Assign to OpenTrain job…
          </Button>
        </div>
      )}
    </div>
  );
};

export const GeneralSettings = () => {
  const { project, fetchProject } = useContext(ProjectContext);

  const updateProject = useCallback(() => {
    if (project.id) fetchProject(project.id, true);
  }, [project]);

  const colors = ["#FDFDFC", "#FF4C25", "#FF750F", "#ECB800", "#9AC422", "#34988D", "#617ADA", "#CC6FBE"];

  const samplings = [
    { value: "Sequential", label: "Sequential", description: "Tasks are ordered by Task ID" },
    { value: "Uniform", label: "Random", description: "Tasks are chosen with uniform random" },
  ];

  const purposes = [
    {
      value: "screening",
      label: "Screening assessment",
      description: "A small fixed task set; every applicant completes the same tasks",
    },
    {
      value: "production",
      label: "Production labeling",
      description: "Real labeling work; tasks are distributed across your workers",
    },
  ];

  return (
    <div className={cn("general-settings").toClassName()}>
      <div className={cn("general-settings").elem("wrapper").toClassName()}>
        <h1>General Settings</h1>
        <div className={cn("settings-wrapper").toClassName()}>
          <Form action="updateProject" formData={{ ...project }} params={{ pk: project.id }} onSubmit={updateProject}>
            <Form.Row columnCount={1} rowGap="16px">
              <Input name="title" label="Project Name" />

              <TextArea name="description" label="Description" style={{ minHeight: 128 }} />
              <RadioGroup name="color" label="Color" size="large" labelProps={{ size: "large" }}>
                {colors.map((color) => (
                  <RadioGroup.Button key={color} value={color}>
                    <div className={cn("color").toClassName()} style={{ "--background": color }} />
                  </RadioGroup.Button>
                ))}
              </RadioGroup>

              <RadioGroup label="Task Sampling" labelProps={{ size: "large" }} name="sampling" simple>
                {samplings.map(({ value, label, description }) => (
                  <RadioGroup.Button
                    key={value}
                    value={`${value} sampling`}
                    label={`${label} sampling`}
                    description={description}
                  />
                ))}
              </RadioGroup>

              <RadioGroup label="Project Purpose" labelProps={{ size: "large" }} name="purpose" simple>
                {purposes.map(({ value, label, description }) => (
                  <RadioGroup.Button key={value} value={value} label={label} description={description} />
                ))}
              </RadioGroup>
            </Form.Row>

            <Form.Actions>
              <Form.Indicator>
                <span case="success">Saved!</span>
              </Form.Indicator>
              <Button type="submit" className="w-[150px]" aria-label="Save general settings">
                Save
              </Button>
            </Form.Actions>
          </Form>
        </div>
        <OpenTrainJobSection project={project} fetchProject={fetchProject} />
      </div>
    </div>
  );
};

GeneralSettings.menuItem = "General";
GeneralSettings.path = "/";
GeneralSettings.exact = true;
