import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { OperatorUnlockForm } from "../components/operator-unlock-form";
import {
  getOperatorSessionFromCookieValue,
  OPERATOR_SESSION_COOKIE_NAME,
} from "../lib/server/operator-session";

export default async function UnlockPage() {
  const cookieStore = await cookies();
  const sessionCookie = cookieStore.get(OPERATOR_SESSION_COOKIE_NAME)?.value;
  if (getOperatorSessionFromCookieValue(sessionCookie)) {
    redirect("/missions");
  }

  return (
    <main id="main-content" className="unlock-page">
      <OperatorUnlockForm />
    </main>
  );
}
