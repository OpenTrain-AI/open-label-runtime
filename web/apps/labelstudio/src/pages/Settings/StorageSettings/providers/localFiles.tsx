import { z } from "zod";
import type { ProviderConfig } from "@humansignal/app-common/blocks/StorageProviderForm/types/provider";
import { IconFolderOpen } from "@humansignal/icons";
import { Alert, AlertDescription, AlertTitle } from "@humansignal/shad/components/ui/alert";

const localFilesDocumentRoot =
  typeof window === "undefined" ? undefined : window.APP_SETTINGS?.local_files_document_root;
const localFilesServingEnabled =
  typeof window === "undefined" ? true : window.APP_SETTINGS?.local_files_serving_enabled !== false;
const trimTrailingSeparators = (value?: string) => value?.replace(/[/\\]+$/, "");
const defaultPathExample = localFilesDocumentRoot
  ? `${trimTrailingSeparators(localFilesDocumentRoot)}/your-subdirectory`
  : undefined;

const pathSchema = defaultPathExample
  ? z.string().min(1, "Path is required").default(defaultPathExample)
  : z.string().min(1, "Path is required");

const LocalFilesServingWarning = () => {
  if (localFilesServingEnabled) return null;
  // The runtime is managed by OpenTrain; users cannot change server env vars,
  // so direct them to support instead of upstream self-hosting docs.
  return (
    <Alert variant="destructive">
      <AlertTitle>Local file serving is disabled</AlertTitle>
      <AlertDescription>
        Local Files storage is not enabled on this Open Label environment. If you need it,{" "}
        <a href="mailto:support@opentrain.ai">contact OpenTrain support</a>.
      </AlertDescription>
    </Alert>
  );
};

export const localFilesProvider: ProviderConfig = {
  name: "localfiles",
  title: "Local Files",
  description: "Configure your local file storage connection with all required Open Label settings",
  icon: () => (
    <IconFolderOpen
      width={40}
      height={40}
      style={{
        color: "var(--color-accent-canteloupe-base)",
        filter: "drop-shadow(0px 0px 12px var(--color-accent-canteloupe-base))",
      }}
    />
  ),
  fields: [
    {
      name: "serving_warning",
      type: "message",
      content: LocalFilesServingWarning,
    },
    {
      name: "path",
      type: "text",
      label: "Absolute local path",
      required: true,
      placeholder: defaultPathExample || "/data/my-folder/subdirectory",
      schema: pathSchema,
      defaultValue: defaultPathExample,
      description: `This path must be an absolute path on the host machine where Open Label is running and start with \n"${localFilesDocumentRoot}" (LOCAL_FILES_DOCUMENT_ROOT).`,
    },
  ],
  layout: [{ fields: ["serving_warning"] }, { fields: ["path"] }],
};

export default localFilesProvider;
