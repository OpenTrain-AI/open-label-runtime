/** Placeholder for the CustomInterface/ReactCode tag, which has no implementation in this fork. **/

import { types } from "mobx-state-tree";
import { observer } from "mobx-react";
import Registry from "../core/Registry";
import ControlBase from "./control/Base";

const CustomInterfaceModel = types.compose(
  "CustomInterfaceModel",
  ControlBase,
  types.model({
    type: "custominterface",
  }),
);

const Code = ({ children }) => (
  <code className="text-sm font-mono bg-neutral-surface border border-neutral-border rounded px-tighter py-tightest">
    {children}
  </code>
);

if (!Registry.models.custominterface) {
  const CustomComponentWrapper = observer(({ item }) => {
    return (
      <div className="py-base">
        The <Code>{item.type === "custominterface" ? "CustomInterface" : "React"}</Code> tag is not supported in Open
        Label.
      </div>
    );
  });

  Registry.addTag("custominterface", CustomInterfaceModel, CustomComponentWrapper);
  Registry.addObjectType(CustomInterfaceModel);
}
