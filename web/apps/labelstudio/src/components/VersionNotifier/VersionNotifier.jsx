import { format } from "date-fns";
import { createContext, useCallback, useContext, useEffect, useReducer } from "react";
import { Link } from "react-router-dom";
import { useAPI } from "../../providers/ApiProvider";
import { cn } from "../../utils/bem";
import "./VersionNotifier.prefix.css";

const VersionContext = createContext();

export const VersionProvider = ({ children }) => {
  const api = useAPI();

  const [state, dispatch] = useReducer((state, action) => {
    if (action.type === "fetch-version") {
      return { ...state, ...action.payload };
    }
  });

  const fetchVersion = useCallback(async () => {
    const response = await api.callApi("version");

    if (response !== null) {
      const data = response["label-studio-os-package"];

      dispatch({
        type: "fetch-version",
        payload: {
          version: data.version,
          latestVersion: data.latest_version_from_pypi,
          newVersion: data.current_version_is_outdated,
          updateTime: format(new Date(data.latest_version_upload_time), "MMM d"),
        },
      });
    }
  }, []);

  useEffect(() => {
    fetchVersion();
  }, []);

  return <VersionContext.Provider value={state}>{children}</VersionContext.Provider>;
};

export const VersionNotifier = ({ showCurrentVersion }) => {
  // The "new version available" upsell linked to labelstud.io — the runtime is
  // managed by OpenTrain, so upgrade prompts are noise; only show the version.
  const { version } = useContext(VersionContext) ?? {};

  return version && showCurrentVersion ? (
    <Link className={cn("current-version").toClassName()} to="/version" target="_blank">
      v{version}
    </Link>
  ) : null;
};
