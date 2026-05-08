import { redirect } from "next/navigation";

export default function SettingsAiPage() {
  redirect("/ai-usage?tab=import-mapping");
}
