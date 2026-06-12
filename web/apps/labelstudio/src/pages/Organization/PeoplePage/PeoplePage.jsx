import { useCallback, useMemo, useState } from "react";
import { useUpdatePageTitle } from "@humansignal/core";
import { cn } from "../../../utils/bem";
import { FF_LSDV_E_297, isFF } from "../../../utils/feature-flags";
import { PeopleList } from "./PeopleList";
import "./PeoplePage.prefix.css";
import { SelectedUser } from "./SelectedUser";

// Membership is managed by OpenTrain: anyone assigned to a project on
// app.opentrain.ai automatically has access here. No invites, no signups.
export const PeoplePage = () => {
  const [selectedUser, setSelectedUser] = useState(null);

  useUpdatePageTitle("People");

  const selectUser = useCallback(
    (user) => {
      setSelectedUser(user);

      localStorage.setItem("selectedUser", user?.id);
    },
    [setSelectedUser],
  );

  const defaultSelected = useMemo(() => {
    return localStorage.getItem("selectedUser");
  }, []);

  return (
    <div className={cn("people").toClassName()}>
      <div className={cn("people").elem("content").toClassName()}>
        <PeopleList
          selectedUser={selectedUser}
          defaultSelected={defaultSelected}
          onSelect={(user) => selectUser(user)}
        />

        {selectedUser ? (
          <SelectedUser user={selectedUser} onClose={() => selectUser(null)} />
        ) : (
          isFF(FF_LSDV_E_297) && (
            <div className="flex h-full flex-col justify-between rounded-2xl border border-neutral-border bg-neutral-background p-6">
              <div>
                <h2 className="text-lg font-semibold">Team access is managed in OpenTrain</h2>
                <p className="mt-3 text-sm text-neutral-content-subtle">
                  Everyone assigned to your projects on OpenTrain automatically has access here — there is nothing to
                  invite or set up. Manage your team and project assignments from your OpenTrain dashboard.
                </p>
              </div>
              <div className="mt-6 text-sm text-neutral-content-subtle">
                Need access or permission help?{" "}
                <a href="mailto:support@opentrain.ai" className="underline hover:no-underline">
                  Contact OpenTrain support
                </a>
                .
              </div>
            </div>
          )
        )}
      </div>
    </div>
  );
};

PeoplePage.title = "People";
PeoplePage.path = "/";
