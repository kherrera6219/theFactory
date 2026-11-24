import { redirect } from "next/navigation";

// /dashboard used to render a second copy of Home under a different header
// (and no sidebar item highlighted). Keep old links working.
export default function DashboardRedirect() {
  redirect("/");
}
