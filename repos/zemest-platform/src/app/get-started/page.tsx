import { AuthPage } from "@/components/site/auth-page";

export const metadata = {
  title: "Get Started — Zemest",
  description: "Create your Zemest account and build your first moderation agent in less than 5 minutes.",
};

export default function GetStartedPage() {
  return <AuthPage mode="get-started" />;
}
