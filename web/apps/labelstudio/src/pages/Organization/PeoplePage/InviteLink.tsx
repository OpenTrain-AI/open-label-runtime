import { Button, Typography } from "@humansignal/ui";
import { Space } from "@humansignal/ui/lib/space/space";
import { cn } from "apps/labelstudio/src/utils/bem";
import { Modal } from "apps/labelstudio/src/components/Modal/ModalPopup";
import { API } from "apps/labelstudio/src/providers/ApiProvider";
import { atom, useAtomValue, useSetAtom } from "jotai";
import { atomWithQuery } from "jotai-tanstack-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { Input } from "../../../components/Form";

const inviteModalVisibleAtom = atom(false);

// Lazy: resetting the token mutates server state, so it must only fire when
// the invite modal is actually opened — not on every Organization page render.
const linkAtom = atomWithQuery((get) => ({
  queryKey: ["invite-link"],
  enabled: get(inviteModalVisibleAtom),
  retry: false,
  async queryFn() {
    const result = await API.invoke("resetInviteLink");
    if (!result?.invite_url) throw new Error("Invite link unavailable");
    return location.origin + result.invite_url;
  },
}));

export function InviteLink({
  opened,
  onOpened,
  onClosed,
}: {
  opened: boolean;
  onOpened?: () => void;
  onClosed?: () => void;
}) {
  const modalRef = useRef<Modal>();
  const setInviteModalVisible = useSetAtom(inviteModalVisibleAtom);
  useEffect(() => {
    setInviteModalVisible(opened);
    if (modalRef.current && opened) {
      modalRef.current?.show?.();
    } else if (modalRef.current && modalRef.current.visible) {
      modalRef.current?.hide?.();
    }
  }, [opened]);

  return (
    <Modal
      ref={modalRef}
      title="Invite members"
      opened={opened}
      bareFooter={true}
      body={<InvitationModal />}
      footer={<InvitationFooter />}
      style={{ width: 640, height: 472 }}
      onHide={onClosed}
      onShow={onOpened}
    />
  );
}

const InvitationModal = () => {
  const { data: link, isError } = useAtomValue(linkAtom);
  return (
    <div className={cn("invite").toClassName()}>
      {isError ? (
        <Typography size="small" className="text-negative-content">
          We couldn't generate an invite link right now. Try the Reset Link button, or contact{" "}
          <a href="mailto:support@opentrain.ai" target="_blank" rel="noreferrer" className="underline">
            support@opentrain.ai
          </a>
          .
        </Typography>
      ) : (
        <Input value={link ?? ""} style={{ width: "100%" }} readOnly />
      )}
      <Typography size="small" className="text-neutral-content-subtler mt-base mb-wider">
        Invite teammates to your Open Label workspace. People that you invite have full access to your active projects.
        Need help with access or onboarding?{" "}
        <a
          href="mailto:support@opentrain.ai"
          target="_blank"
          rel="noreferrer"
          className="hover:underline"
          onClick={() =>
            __lsa("docs.organization.add_people.learn_more", {
              href: "mailto:support@opentrain.ai",
            })
          }
        >
          Contact support
        </a>
        .
      </Typography>
    </div>
  );
};

const InvitationFooter = () => {
  const { copyText, copied } = useTextCopy();
  const { refetch, data: link } = useAtomValue(linkAtom);

  return (
    <Space spread>
      <Space>
        <Button
          variant="negative"
          look="outlined"
          style={{ width: 170 }}
          onClick={() => refetch()}
          aria-label="Refresh invite link"
        >
          Reset Link
        </Button>
      </Space>
      <Space>
        <Button
          variant={copied ? "positive" : "primary"}
          className="w-[170px]"
          onClick={() => copyText(link!)}
          aria-label="Copy invite link"
        >
          {copied ? "Copied!" : "Copy link"}
        </Button>
      </Space>
    </Space>
  );
};

function useTextCopy() {
  const [copied, setCopied] = useState(false);

  const copyText = useCallback((value: string) => {
    setCopied(true);
    navigator.clipboard.writeText(value ?? "");
    setTimeout(() => setCopied(false), 1500);
  }, []);

  return { copied, copyText };
}
