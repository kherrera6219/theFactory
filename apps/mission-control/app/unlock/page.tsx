import { redirect } from "next/navigation";

// Local Mission Control starts unlocked. Keep this redirect so bookmarked or
// linked /unlock URLs land on the Settings runtime/key configuration page.
export default function UnlockPage() {
  redirect("/settings");
}
