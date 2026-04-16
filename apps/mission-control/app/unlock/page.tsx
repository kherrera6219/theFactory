import { redirect } from "next/navigation";

// The operator unlock form has moved to Settings → Operator Admin Session.
// This route now redirects so any bookmarked or linked /unlock URLs still work.
export default function UnlockPage() {
  redirect("/settings");
}
