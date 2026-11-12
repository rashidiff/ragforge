import * as AlertDialog from "@radix-ui/react-alert-dialog";
import type { Chat } from "../lib/contracts";
import { useLocale } from "../lib/i18n";

interface Props {
  chat: Chat | null;
  busy: boolean;
  error: string;
  onCancel: () => void;
  onConfirm: () => Promise<void>;
}

export function DeleteChatDialog({ chat, busy, error, onCancel, onConfirm }: Props) {
  const { t } = useLocale();
  return <AlertDialog.Root open={chat !== null} onOpenChange={(open) => { if (!open && !busy) onCancel(); }}>
    <AlertDialog.Portal>
      <AlertDialog.Overlay className="dialog-overlay" />
      <AlertDialog.Content className="dialog-content" onEscapeKeyDown={(event) => { if (busy) event.preventDefault(); }}>
        <AlertDialog.Title>{t("Delete this chat?")}</AlertDialog.Title>
        <AlertDialog.Description>
          “{chat?.title}” {t("and its conversation memory will be removed. Local backups may still contain it. Other chats and your PDF Library are preserved.")}
        </AlertDialog.Description>
        {error && <p role="alert" className="error">{error}</p>}
        <div className="dialog-actions">
          <AlertDialog.Cancel asChild><button disabled={busy} onClick={onCancel}>{t("Cancel")}</button></AlertDialog.Cancel>
          <button className="danger" disabled={busy} onClick={() => void onConfirm()}>
            {t(busy ? "Deleting…" : "Delete chat")}
          </button>
        </div>
      </AlertDialog.Content>
    </AlertDialog.Portal>
  </AlertDialog.Root>;
}
